import re
import requests
import json
import logging
import pandas as pd
import math
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any
from backend.services.azure_blob import AzureBlobService
from backend.services.cosmos_db import CosmosLeadGenClient
from backend.utils.discorderrorreporter import DiscordErrorReporter
from exa_py import Exa
import asyncio


class LeadGenService:
    """Service for handling lead generation and property scraping"""
    
    def __init__(self, api_key: str, exa_api_key, cosmos_client: CosmosLeadGenClient, azure_blob_config: dict, discord_reporter: DiscordErrorReporter):
        self.api_key = api_key
        self.exa_api_key = exa_api_key
        self.cosmos_client = cosmos_client
        self.blob_service = AzureBlobService(azure_blob_config)
        self.discord_reporter = discord_reporter
        
        self.columns_to_keep = [
            'addressStreet', 'addressCity', 'addressState', 'addressZipcode',
            'beds', 'baths', 'lotAreaValue', 'lotAreaUnit',
            'price', 'address', 'detailUrl',
        ]
        
        self.column_mapping = {
            'address': 'Full Address',
            'addressCity': 'City',
            'price': 'Asking Price',
            'detailUrl': 'Property URL',
            'addressStreet': 'Address',
            'addressState': 'State',
            'addressZipcode': 'Zip',
            'beds': 'Beds',
            'baths': 'Bathrooms',
            'lotAreaValue': 'Lot Size',
            'lotAreaUnit': 'Lot Unit'
        }

        
    
    #---------------------------------ZILLOW START---------------------------------------------#

    '''
    get_zillow_comp_properties - function to get all the property listings on zillow based on the URL
    @params - input_url: the zillow url with all the preset neccessary parameters 
    @return - property_listings: an array of dicts that contains all the zillow properties from the page source  
    '''

    async def get_zillow_comp_properties(self, input_url: str) -> list:
        """
        Fetches property data from a single page URL.
        Mimics the original functionality of get_zillow_properties.
        """
        try:
            # GET request to fetch the HTML content
            content = await self._fetch_page_content(input_url)
            soup = BeautifulSoup(content, 'html.parser')

            # Find all script tags containing the data
            script_tags = soup.find_all('script')

            # Define a regex to match the property data inside the script tag
            search_results_pattern = re.compile(r'"searchResults":(\{.*?\}\}\})', re.DOTALL)

            # Search through script tags for the required key
            for script in script_tags:
                script_content = script.string
                if script_content:
                    match = search_results_pattern.search(script_content)
                    if match:
                        # Parse the matched data
                        search_results_data = match.group(1)
                        search_results_json = json.loads(f'{{"searchResults": {search_results_data[:-1]}}}')
                        property_listings = search_results_json['searchResults']['listResults']

                        for listing in property_listings:
                            listing.pop('imgSrc', None)  # Using pop with None as default value in case key doesn't exist
                            listing.pop('carouselPhotos', None)
                            listing.pop('hdpData', None)
                        return property_listings  # Return listings for this page

            return []  # Return an empty list if no results are found
        except Exception as e:
            logging.error(f"Error fetching or parsing Zillow properties: {str(e)}")
            error_context = {
                'service': 'LeadGenService',
                'method': 'get_zillow_comp_properties',
                'input_url': input_url
            }
            await self.discord_reporter.report_error(e, error_context)
            return []
        
    '''
    get_subj_property - function to get the details of a subject property from a web search
    @return - property: a json string with details of the property.  
    '''
    async def get_subj_property(self, prompt: str) -> list:
        exa = Exa(api_key = self.exa_api_key)
        result = exa.search_and_contents(
            prompt,
            text = {
                "max_characters": 1000
            },
            type = "keyword"
        )

        return f"Search results: {result}\n\n{prompt}"

    async def _fetch_page_content(self, url: str) -> Optional[bytes]:
        """
        Helper method to fetch content using ScrapingBee API
        """
        try:
            response = requests.get(
                url='https://app.scrapingbee.com/api/v1/',
                params={
                    'api_key': self.api_key,
                    'url': url,
                    'premium_proxy': 'true',
                    'country_code': 'us',
                    'render_js': 'false'
                }
            )
            return response.content
        except Exception as error:
            logging.error(f"Error fetching content: {str(error)}")
            return None
            

    def _parse_property_data(self, html_content: bytes) -> pd.DataFrame:
        """
        Helper method to parse property data from HTML content
        """
        if not html_content:
            return pd.DataFrame()

        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            script_tags = soup.find_all('script')
            search_results_pattern = re.compile(r'"searchResults":(\{.*?\}\}\})', re.DOTALL)

            for script in script_tags:
                script_content = script.string
                if not script_content:
                    continue

                match = search_results_pattern.search(script_content)
                if not match:
                    continue

                search_results_data = match.group(1)
                search_results_json = json.loads(f'{{"searchResults": {search_results_data[:-1]}}}')
                property_listings = search_results_json['searchResults']['listResults']

                if not property_listings:
                    continue

                # Flatten nested data in `hdpData.homeInfo`
                for listing in property_listings:
                    home_info = listing.get("hdpData", {}).get("homeInfo", {})
                    listing["lotAreaValue"] = home_info.get("lotAreaValue")
                    listing["lotAreaUnit"] = home_info.get("lotAreaUnit")

                df_out = pd.DataFrame(property_listings)
                
                # Initialize DataFrame with required columns
                final_df = pd.DataFrame(columns=[self.column_mapping[col] for col in self.columns_to_keep])
                
                # Only keep available columns
                available_columns = [col for col in self.columns_to_keep if col in df_out.columns]
                if not available_columns:
                    logging.warning("No matching columns found in the data")
                    return final_df
                
                # Copy data for available columns
                for col in available_columns:
                    final_df[self.column_mapping[col]] = df_out[col]
                
                return final_df

            return pd.DataFrame(columns=[self.column_mapping[col] for col in self.columns_to_keep])
            
        except Exception as e:
            logging.error(f"Error parsing property data: {str(e)}")
            return pd.DataFrame(columns=[self.column_mapping[col] for col in self.columns_to_keep])

    async def fetch_page_data(self, input_url: str, page: int) -> pd.DataFrame:
        """Fetch data for a single page"""
        logging.info(f"Fetching data for page {page}...")
        
        try:
            # Construct paginated URL
            if page == 1:
                paginated_url = input_url
            else:
                base_url, query_string = input_url.split('?')
                paginated_url = f"{base_url}{page}_p/?{query_string}"
            
            # Update pagination in query string
            paginated_url = paginated_url.replace(
                '"pagination":{}',
                f'"pagination":{{"currentPage":{page}}}'
            )
            
            content = await self._fetch_page_content(paginated_url)
            return self._parse_property_data(content)
            
        except Exception as e:
            logging.error(f"Error fetching page data: {str(e)}")
            return pd.DataFrame(columns=[self.column_mapping[col] for col in self.columns_to_keep])

    def _get_total_results(self, content: bytes) -> int:
        """Extract total results from the first page"""
        try:
            soup = BeautifulSoup(content, 'html.parser')
            results_tag = soup.find('span', class_='result-count')
            if results_tag:
                return int(results_tag.text.split()[0])
            return 0
        except Exception as e:
            logging.error(f"Error getting total results: {str(e)}")
            return 0

    def _calculate_needed_pages(self, total_results: int, results_per_page: int = 41) -> int:
        """Calculate needed pages, rounding up"""
        return math.ceil(total_results / results_per_page)

    async def get_all_pages(self, input_url: str, max_threads: int = 5, max_pages: int = 5) -> pd.DataFrame:
        """Fetch all pages of property data""" 
        try:
            # Fetch first page
            first_page_content = await self._fetch_page_content(input_url)
            first_page_data = self._parse_property_data(first_page_content)
            
            total_results = self._get_total_results(first_page_content)
            needed_pages = min(self._calculate_needed_pages(total_results), max_pages)
            
            logging.info(f"Found {total_results} results, limiting to {needed_pages} pages")
            
            if needed_pages <= 1:
                return first_page_data
            
            # Fetch remaining pages
            all_properties = [first_page_data]
            
            # Create tasks for concurrent async fetching
            tasks = [
                self.fetch_page_data(input_url, page)
                for page in range(2, needed_pages + 1)
            ]
            
            # Run tasks concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for properties in results:
                if isinstance(properties, Exception):
                    logging.error(f"Error fetching page data: {str(properties)}")
                    continue
                if isinstance(properties, pd.DataFrame) and not properties.empty:
                    all_properties.append(properties)

            if all_properties:
                return pd.concat(all_properties, ignore_index=True)
            return pd.DataFrame(columns=[self.column_mapping[col] for col in self.columns_to_keep])
            
        except Exception as e:
            logging.error(f"Error getting all pages: {str(e)}")
            return pd.DataFrame(columns=[self.column_mapping[col] for col in self.columns_to_keep])
        

    def _parse_attorneys_to_df(self, content: str) -> pd.DataFrame:
        # Parse the HTML content
        soup = BeautifulSoup(content, 'html.parser')
        
        # Find all JSON-LD script tags
        script_tags = soup.find_all('script', {'type': 'application/ld+json'})
        
        # Find the script tag containing @graph
        attorney_data = None
        for script in script_tags:
            try:
                data = json.loads(script.string)
                if '@graph' in data:
                    attorney_data = data
                    break
            except json.JSONDecodeError:
                continue
        
        if not attorney_data:
            return pd.DataFrame()  # Return empty DataFrame if no data found
        
        # Extract attorneys data from @graph
        attorneys = attorney_data['@graph']
        
        # Create a list to store processed attorney data
        processed_data = []
        
        for attorney in attorneys:
            data = {
                'name': attorney['name'].strip(),
                'telephone': attorney['telephone'],
                'website': attorney.get('url', ''),  # Using get() in case url is missing
                'street_address': attorney['address'].get('streetAddress', ''),
                'city': attorney['address']['addressLocality'],
                'state': attorney['address']['addressRegion'],
                'zip': attorney['address']['postalCode']
            }
            processed_data.append(data)
        
        # Create DataFrame
        df = pd.DataFrame(processed_data)
        
        return df
    
    async def get_all_attorneys(self, input_url: str) -> pd.DataFrame:
        """Fetch all pages of property data"""
        try:
            response = requests.get(
                url='https://app.scrapingbee.com/api/v1/',
                params={
                    'api_key': self.api_key,
                    'url': input_url,
                    'premium_proxy': 'true',
                    'country_code': 'us',
                    'render_js': 'false'
                }
            )
            
            df = self._parse_attorneys_to_df(response.content)
            
            return df
        except Exception as error:
            logging.error(f"Error fetching content: {str(error)}")
            return None
        
    async def get_properties(self, url: str, filename: str) -> str:
        """Get property data from URL or cache"""
        try:
            # Check cache first
            cached_data = await self.cosmos_client.get_cached_data(url)
            if cached_data:
                logging.info("Using cached lead data")
                df_properties = pd.DataFrame(json.loads(cached_data["data"]))
                preview = AzureBlobService.get_dataframe_preview(df_properties)
                return (
                    f"The link to the full list of properties requested is located here. "
                    f"Link: {cached_data['excel_link']} Here's a few properties from the requested list. "
                    f"List: {preview}"
                )

            # Fetch new data if no cache
            logging.info("Fetching new lead data")
            df_properties = await self.get_all_pages(url)
            
            if df_properties.empty:
                return "No leads were found"

            # Generate Excel file and cache data
            timestamp = datetime.now(timezone.utc).isoformat()
            excel_link = self.blob_service.upload_dataframe(
                container_name="leads",
                file_name=filename,
                df=df_properties
            )

            # Cache the data
            data_to_cache = {
                "data": json.dumps(df_properties.to_dict(orient="records")),
                "excel_link": excel_link
            }
            await self.cosmos_client.write_to_cache(url, data_to_cache, timestamp)

            # Generate preview
            preview = AzureBlobService.get_dataframe_preview(df_properties)
            return (
                f"The link to the full list of leads is located here. "
                f"Link: {excel_link} Here's a few leads from the list. "
                f"List: {preview}"
            )

        except Exception as e:
            logging.error(f"Error getting properties: {str(e)}")
            error_context = {
                'service': 'LeadGenService',
                'method': 'get_properties',
                'url': url,
                'filename': filename
            }
            await self.discord_reporter.report_error(e, error_context)
            return "An error occurred while fetching leads"
        
        
    async def get_attorneys(self, url: str, filename: str) -> str:
        """Get property data from URL or cache"""
        try:
            # Check cache first
            cached_data = await self.cosmos_client.get_cached_data(url)
            if cached_data:
                logging.info("Using cached lead data")
                df_attorneys = pd.DataFrame(json.loads(cached_data["data"]))
                preview = AzureBlobService.get_dataframe_preview(df_attorneys)
                return (
                    f"The link to the full list of attorneys is located here. "
                    f"Link: {cached_data['excel_link']} Here's are a few attorneys from the list. "
                    f"List: {preview}"
                )

            # Fetch new data if no cache
            logging.info("Fetching new attorneys data")
            df_attorneys = await self.get_all_attorneys(url)
            
            if df_attorneys is None or df_attorneys.empty:
                return "No attorneys were found"

            # Generate Excel file and cache data
            timestamp = datetime.now(timezone.utc).isoformat()
            excel_link = self.blob_service.upload_dataframe(
                container_name="leads",
                file_name=filename,
                df=df_attorneys
            )

            # Cache the data
            data_to_cache = {
                "data": json.dumps(df_attorneys.to_dict(orient="records")),
                "excel_link": excel_link
            }
            await self.cosmos_client.write_to_cache(url, data_to_cache, timestamp)

            # Generate preview
            preview = AzureBlobService.get_dataframe_preview(df_attorneys)
            return (
                f"The link to the full list of leads is located here. "
                f"Link: {excel_link} Here's a few leads from the list. "
                f"List: {preview}"
            )

        except Exception as e:
            logging.error(f"Error getting properties: {str(e)}")
            return "An error occurred while fetching leads"
        
    async def get_bricked_comps(self, full_address: str, max_comps: int = 12) -> dict:
        """
        Calls Bricked API with an address and returns a trimmed payload ready for chat completion context.
        Tries common parameter/body patterns because the spec example is ambiguous (GET /property/create).
        """

        api_key = os.getenv("BRICKED_API_KEY")
        if not api_key:
            raise RuntimeError("BRICKED_API_KEY environment variable is not set.")

        url = "https://api.bricked.ai/v1/property/create"
        headers = {"x-api-key": api_key}

        def _do_request(method: str, **kwargs):
            return requests.request(method, url, headers=headers, timeout=45, **kwargs)

        # Try a few likely request shapes
        attempts = [
            ("GET",  {"params": {"address": full_address}}),
            ("GET",  {"params": {"property_address": full_address}}),
            ("POST", {"json": {"address": full_address}}),
            ("POST", {"json": {"fullAddress": full_address}}),
            ("POST", {"json": {"property_address": full_address}}),
        ]

        last_err = None
        resp = None

        for method, kwargs in attempts:
            try:
                resp = await asyncio.to_thread(_do_request, method, **kwargs)
                if resp.status_code >= 200 and resp.status_code < 300:
                    break
            except Exception as e:
                last_err = e
                resp = None

        if resp is None:
            raise RuntimeError(f"Failed to call Bricked API. Last error: {last_err}")

        if resp.status_code < 200 or resp.status_code >= 300:
            raise RuntimeError(
                f"Bricked API error {resp.status_code}: {resp.text[:1000]}"
            )

        data = resp.json()

        # ---- Trim payload for chat completion ----
        prop = data.get("property") or {}
        prop_addr = (prop.get("address") or {}).get("fullAddress") or full_address

        def pick_details(d: dict) -> dict:
            d = d or {}
            return {
                "bedrooms": d.get("bedrooms"),
                "bathrooms": d.get("bathrooms"),
                "squareFeet": d.get("squareFeet"),
                "yearBuilt": d.get("yearBuilt"),
                "lotSquareFeet": d.get("lotSquareFeet"),
                "stories": d.get("stories"),
                "lastSaleDate": d.get("lastSaleDate"),
                "lastSaleAmount": d.get("lastSaleAmount"),
                "daysOnMarket": d.get("daysOnMarket"),
                "marketStatus": d.get("marketStatus"),
            }

        comps_in = data.get("comps") or []
        comps_out = []
        for c in comps_in[:max_comps]:
            c_addr = (c.get("address") or {}).get("fullAddress")
            comps_out.append({
                "address": c_addr,
                "details": pick_details(c.get("details") or {}),
                "adjusted_value": c.get("adjusted_value"),
                "selected": c.get("selected"),
                "compType": c.get("compType"),
                "listingType": c.get("listingType"),
            })

        trimmed = {
            "subject": {
                "address": prop_addr,
                "details": pick_details((prop.get("details") or {})),
                "latitude": prop.get("latitude"),
                "longitude": prop.get("longitude"),
            },
            "arv": data.get("arv"),
            "cmv": data.get("cmv"),
            "shareLink": data.get("shareLink"),
            "dashboardLink": data.get("dashboardLink"),
            "comps": comps_out,
        }

        return trimmed
