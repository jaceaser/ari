# chat_handler.py
# Drop-in, full file with persistent session memory + context budgeting.
# Preserves your logging / error reporting scaffolding and classification flow.

import asyncio
import logging
import uuid
import json
import pandas as pd
import re
from datetime import datetime
from typing import Dict, AsyncGenerator, List, Any, Tuple, Optional
from backend.services.azure_blob import AzureBlobService
from backend.utils.formatting import format_stream_response # your project utility

# -------------------------------------------------------------------------------

class ChatHandler:
    def __init__(
        self,
        openai_service,
        cosmos_service,
        lead_gen_service,
        prompt_configs,
        discord_reporter,
        tier: str = "ari_pro"
    ):
        self.openai_service = openai_service
        self.cosmos_service = cosmos_service
        self.lead_gen_service = lead_gen_service
        self.prompt_configs = prompt_configs
        self.discord_reporter = discord_reporter
        self.tier = (tier or "ari_pro").strip()

        # Route-specific token budgets (input caps; reserve is for completion)
        self.ROUTE_BUDGETS = {
            "Strategy":  {"total_cap": 6000, "reserve": 1200, "summary": 400, "recent": 600,  "context": 1200},
            "Education": {"total_cap": 12000,"reserve": 1500, "summary": 600, "recent": 1400, "context": 3000},
            "Leads":     {"total_cap": 12000,"reserve": 1500, "summary": 400, "recent": 600,  "context": 6000},
            "Comps":     {"total_cap": 12000,"reserve": 1500, "summary": 400, "recent": 600,  "context": 6000},
            "Contracts": {"total_cap": 8000, "reserve": 1200, "summary": 400, "recent": 600,  "context": 2000},
            "Attorneys": {"total_cap": 9000, "reserve": 1200, "summary": 400, "recent": 800,  "context": 2000},
            "Buyers":    {"total_cap": 9000, "reserve": 1200, "summary": 400, "recent": 800,  "context": 2000},
            "OffTopic":  {"total_cap": 6000, "reserve": 900,  "summary": 300, "recent": 600,  "context": 800},
            "Default":   {"total_cap": 9000, "reserve": 1200, "summary": 500, "recent": 800,  "context": 2000},
        }

    # ===========================
    # Public entrypoint
    # ===========================
    async def handle_conversation(self, request_body: Dict, stream_override: bool = False):
        """
        Entry for /conversation. Handles classification and routes to the right handler,
        preserving the output streaming behavior and your logging.
        """
        try:
            messages = request_body.get("messages", [])
            user_messages = [m for m in messages if m.get('role') == 'user']
            if not user_messages:
                raise Exception("No user messages found in the request")

            prompt = user_messages[-1]["content"]

            history_metadata = request_body.get("history_metadata", {})

            # Tier-based behavior
            if self.tier == "ari_lite":
                # Lite always defaults to Education
                async for chunk in self._handle_education_query(prompt, request_body):
                    yield format_stream_response(chunk, history_metadata)

            elif self.tier == "ari_pro":
                # Normalize classification output
                raw_classification = await self.classify_prompt(prompt)
                classification = (
                    raw_classification.replace("Classification:", "")  # strip noisy prefix
                    .strip()                                           # remove whitespace
                    .title()                                           # normalize case
                )

                if classification not in self.prompt_configs:
                    logging.warning(f"[handle_conversation] Unknown classification '{raw_classification}', defaulting to 'Education'")
                    classification = "Education"

                model_used = self.prompt_configs[classification].azure_config.deployment_name
                logging.info(f"[handle_conversation] Model used for '{classification}': {model_used}")

                # Process based on classification
                if classification == "Education":
                    async for chunk in self._handle_education_query(prompt, request_body):
                        yield format_stream_response(chunk, history_metadata)

                elif classification == "Strategy":
                    async for chunk in self._handle_strategy_query(prompt, request_body):
                        yield format_stream_response(chunk, history_metadata)

                elif classification == "Attorneys":
                    async for chunk in self._handle_attorneys_query(prompt, request_body):
                        yield format_stream_response(chunk, history_metadata)

                elif classification == "Comps":
                    async for chunk in self._handle_comps_query(prompt, request_body):
                        yield format_stream_response(chunk, history_metadata)

                elif classification == "Contracts":
                    async for chunk in self._handle_contracts_query(prompt, request_body):
                        yield format_stream_response(chunk, history_metadata)

                elif classification == "Offtopic":
                    async for chunk in self._handle_offtopic_query(prompt, request_body):
                        yield format_stream_response(chunk, history_metadata)

                else:
                    # Default to Education
                    async for chunk in self._handle_education_query(prompt, request_body):
                        yield format_stream_response(chunk, history_metadata)

            elif self.tier == "ari_elite":
                # Normalize classification output
                raw_classification = await self.classify_prompt(prompt)
                classification = (
                    raw_classification.replace("Classification:", "")
                    .strip()
                    .title()
                )

                if classification not in self.prompt_configs:
                    logging.warning(f"[handle_conversation] Unknown classification '{raw_classification}', defaulting to 'Education'")
                    classification = "Education"

                model_used = self.prompt_configs[classification].azure_config.deployment_name
                logging.info(f"[handle_conversation] Model used for '{classification}': {model_used}")

                # Process based on classification
                if classification == "Leads":
                    async for chunk in self._handle_leads_query(prompt, request_body):
                        yield format_stream_response(chunk, history_metadata)

                elif classification == "Education":
                    async for chunk in self._handle_education_query(prompt, request_body):
                        yield format_stream_response(chunk, history_metadata)

                elif classification == "Strategy":
                    async for chunk in self._handle_strategy_query(prompt, request_body):
                        yield format_stream_response(chunk, history_metadata)

                elif classification == "Attorneys":
                    async for chunk in self._handle_attorneys_query(prompt, request_body):
                        yield format_stream_response(chunk, history_metadata)

                elif classification == "Comps":
                    async for chunk in self._handle_comps_query(prompt, request_body):
                        yield format_stream_response(chunk, history_metadata)

                elif classification == "Contracts":
                    async for chunk in self._handle_contracts_query(prompt, request_body):
                        yield format_stream_response(chunk, history_metadata)

                elif classification == "Buyers":
                    async for chunk in self._handle_buyers_query(prompt, request_body):
                        yield format_stream_response(chunk, history_metadata)

                elif classification == "Offtopic":
                    async for chunk in self._handle_offtopic_query(prompt, request_body):
                        yield format_stream_response(chunk, history_metadata)

                else:
                    # Default to Education
                    async for chunk in self._handle_education_query(prompt, request_body):
                        yield format_stream_response(chunk, history_metadata)

            else:
                # Fallback for any other/unexpected tier
                async for chunk in self._handle_education_query(prompt, request_body):
                    yield format_stream_response(chunk, history_metadata)
        except Exception as ex:
            error_context = {
                'service': 'ChatHandler',
                'method': 'handle_conversation',
                'request_messages': request_body.get('messages', [])[-1] if request_body.get('messages') else None
            }
            await self.discord_reporter.report_error(ex, error_context)
            logging.exception("Error in conversation handler")
            yield {"error": str(ex)}

    # ===========================
    # Classification
    # ===========================
    async def classify_prompt(self, prompt: str, request_body: Dict = None) -> str:
        """Classify the type of prompt. Keeps last 3 user messages for signal."""
        try:
            messages = [{"role": "system", "content": self.prompt_configs['Classification'].system_message}]
            if request_body:
                history = request_body.get("messages", [])
                context_messages = [msg for msg in history if msg.get("role") == "user"]
                messages.extend(context_messages[-3:])
            else:
                messages.append({"role": "user", "content": prompt})

            async for response in self.openai_service.create_chat_completion(
                messages=messages,
                prompt_config=self.prompt_configs['Classification']
            ):
                classification_result = response.choices[0].message.content.strip()
                logging.info(f"[classify_prompt] Classification result: '{classification_result}'")
                break

            return classification_result

        except Exception as e:
            logging.error(f"Error in classification: {str(e)}")
            return "Education"

    # ===========================
    # Route handlers
    # ===========================
    async def _handle_leads_query(self, prompt: str, request_body: Dict) -> AsyncGenerator:
        """Handle leads-related queries; persists route-tagged summary + raw context for this turn."""
        try:
            link_config = self.prompt_configs["LeadsLink"]
            leads_config = self.prompt_configs["Leads"]

            lead_url = await self.openai_service.generate_lead_url(link_config, prompt)
            logging.info(f"Lead URL Generated: {lead_url}")

            results = None
            if self._is_url(lead_url):
                filename = f"leads_{uuid.uuid4().hex}.xlsx"
                results = await self.lead_gen_service.get_properties(lead_url, filename)

                # Retry heuristic if empty
                if not results or (isinstance(results, list) and len(results) == 0):
                    logging.warning("Lead URL fetched, but returned 0 results.")
                    modified_prompt = f"{prompt}. Use Houston, Texas as the location."
                    lead_url = await self.openai_service.generate_lead_url(link_config, modified_prompt)
                    filename = f"leads_retry_{uuid.uuid4().hex}.xlsx"
                    results = await self.lead_gen_service.get_properties(lead_url, filename)

            lead_type = self._infer_lead_type_from_url(lead_url)

            request_body = self._add_context_to_request(
                request_body=request_body,
                context_data=results or f"No properties could be retrieved. You can check manually: {lead_url}",
                system_message=leads_config.system_message,
                route="Leads",
                lead_type=lead_type
            )

            async for chunk in self.openai_service.create_chat_completion(
                messages=request_body["messages"],
                prompt_config=leads_config
            ):
                yield chunk

        except Exception as e:
            logging.error(f"Error handling leads query: {str(e)}")
            await self.discord_reporter.report_error(e, {
                'service': 'ChatHandler',
                'method': '_handle_leads_query',
                'prompt': prompt
            })
            raise

    async def _handle_comps_query(self, prompt: str, request_body: Dict) -> AsyncGenerator:
        """Handle comps-related queries; persists route-tagged summary + raw context for this turn."""
        try:
            # comp_link_config = self.prompt_configs["CompLink"]
            comp_config = self.prompt_configs["Comps"]

            # subj_property = await self.lead_gen_service.get_subj_property(prompt)
            # comp_prop_url = await self.openai_service.generate_lead_url(comp_link_config, subj_property)

            # comps = []
            # if self._is_url(comp_prop_url):
            #     comps = await self.lead_gen_service.get_zillow_comp_properties(comp_prop_url)

            address = await self.get_address(prompt)
            bricked = await self.lead_gen_service.get_bricked_comps(address)

            context_blob = json.dumps(bricked, indent=2)
            # feed `context_blob` into your chat completion context


            results = [f"Subject Property: {address} Potential Comparable Properties: {context_blob}"]

            request_body = self._add_context_to_request(
                request_body=request_body,
                context_data=results,
                system_message=comp_config.system_message,
                route="Comps"
            )

            async for chunk in self.openai_service.create_reasoning_chat_completion(
                messages=request_body["messages"],
                prompt_config=comp_config
            ):
                yield chunk

        except Exception as e:
            try:
                comp_link_config = self.prompt_configs["CompLink"]
                comp_config = self.prompt_configs["Comps"]

                subj_property = await self.lead_gen_service.get_subj_property(prompt)
                comp_prop_url = await self.openai_service.generate_lead_url(comp_link_config, subj_property)

                comps = []
                if self._is_url(comp_prop_url):
                    comps = await self.lead_gen_service.get_zillow_comp_properties(comp_prop_url)

                results = [f"Subject Property Address: {address} Subject Property: {subj_property} Potential Comparable Properties: {comps}"]

                request_body = self._add_context_to_request(
                    request_body=request_body,
                    context_data=results,
                    system_message=comp_config.system_message,
                    route="Comps"
                )

                async for chunk in self.openai_service.create_reasoning_chat_completion(
                    messages=request_body["messages"],
                    prompt_config=comp_config
                ):
                    yield chunk
            except Exception as e:
                await self.discord_reporter.report_error(e, {
                    'service': 'ChatHandler',
                    'method': '_handle_comps_query',
                    'prompt': prompt
                })
                logging.error(f"Error handling comps query: {str(e)}")
                raise

    async def _handle_attorneys_query(self, prompt: str, request_body: Dict) -> AsyncGenerator:
        """Handle attorney-related queries; persists route-tagged summary + raw context for this turn."""
        try:
            link_config = self.prompt_configs["AttorneysLink"]
            attorneys_config = self.prompt_configs["Attorneys"]

            lead_url = await self.openai_service.generate_lead_url(link_config, prompt)
            filename = f"attorneys_{uuid.uuid4().hex}.xlsx"
            results = await self.lead_gen_service.get_attorneys(lead_url, filename)

            request_body = self._add_context_to_request(
                request_body=request_body,
                context_data=results,
                system_message=attorneys_config.system_message,
                route="Attorneys"
            )

            async for chunk in self.openai_service.create_chat_completion(
                messages=request_body["messages"],
                prompt_config=attorneys_config
            ):
                yield chunk
        except Exception as e:
            await self.discord_reporter.report_error(e, {
                'service': 'ChatHandler',
                'method': '_handle_attorneys_query',
                'prompt': prompt
            })
            logging.error(f"Error handling attorneys query: {str(e)}")
            raise

    async def _handle_strategy_query(self, prompt: str, request_body: Dict) -> AsyncGenerator:
        """Strategy queries: now routed through the budgeted builder to preserve session memory."""
        try:
            config = self.prompt_configs["Strategy"]
            original_messages = request_body.get("messages", [])

            messages = self._build_messages_with_budget(
                route="Strategy",
                system_message=config.system_message,
                original_messages=original_messages,
                retrieved_context=None,
                session_summary=request_body.get("session_summary", "")
            )

            async for chunk in self.openai_service.create_reasoning_chat_completion(
                messages=messages,
                prompt_config=config
            ):
                yield chunk

        except Exception as e:
            await self.discord_reporter.report_error(e, {
                'service': 'ChatHandler',
                'method': '_handle_strategy_query',
                'prompt': prompt
            })
            raise

    async def _handle_education_query(self, prompt: str, request_body: Dict) -> AsyncGenerator:
        """Education queries: preserve prior convo but budgeted."""
        try:
            config = self.prompt_configs["Education"]
            original_messages = request_body.get("messages", [])

            messages = self._build_messages_with_budget(
                route="Education",
                system_message=config.system_message,
                original_messages=original_messages,
                retrieved_context=None,
                session_summary=request_body.get("session_summary", "")
            )

            async for chunk in self.openai_service.create_reasoning_chat_completion(
                messages=messages,
                prompt_config=config
            ):
                yield chunk
        except Exception as e:
            error_context = {
                'service': 'ChatHandler',
                'method': '_handle_education_query',
                'prompt': prompt
            }
            await self.discord_reporter.report_error(e, error_context)
            raise

    async def _handle_contracts_query(self, prompt: str, request_body: Dict) -> AsyncGenerator:
        """Contracts: preserve history; expand last user prompt if you already did before."""
        try:
            config = self.prompt_configs["Contracts"]
            messages = request_body.get("messages", [])

            # Optional: expand last user prompt with your existing logic
            for i in range(len(messages) - 1, -1, -1):
                if messages[i].get("role") == "user":
                    original_prompt = messages[i]["content"]
                    expanded_prompt = await self._expand_contract_prompt(original_prompt)
                    messages[i]["content"] = expanded_prompt
                    break

            # Let messages go through as-is, or route via builder if you prefer:
            # messages = self._build_messages_with_budget(
            #     route="Contracts",
            #     system_message=config.system_message,
            #     original_messages=messages,
            #     retrieved_context=None,
            #     session_summary=request_body.get("session_summary", "")
            # )

            async for chunk in self.openai_service.create_chat_completion(
                messages=messages,
                prompt_config=config
            ):
                yield chunk
        except Exception as e:
            error_context = {
                'service': 'ChatHandler',
                'method': '_handle_contracts_query',
                'prompt': prompt
            }
            await self.discord_reporter.report_error(e, error_context)
            raise

    async def _handle_buyers_query(self, prompt: str, request_body: Dict) -> AsyncGenerator:
        """Handle buyers queries by pulling a random list of buyers from Cosmos and uploading the full list to blob storage."""
        try:
            buyers_config = self.prompt_configs["Buyers"]

            # 1) Extract location (city, state) from the user's prompt
            city, state = await self._extract_city_state_from_prompt(prompt)

            if not city or not state:
                context_data = (
                    "I could not confidently detect a city and state from the user's request. "
                    "Ask the user to rephrase their request with a clear 'City, ST' format, for example: 'Houston, TX'."
                )
            else:
                # 2) Pull buyers from Cosmos (Nationwide buyers container)
                buyers = await self.cosmos_service.get_buyers_by_city_state(city, state, max_results=50)

                if not buyers:
                    context_data = (
                        f"No buyers were found for {city}, {state}. "
                        "Let the user know that there are no matches in the current buyers list "
                        "and suggest trying a nearby market or a different area."
                    )
                else:
                    # Build full dataframe for blob + lightweight preview (name, phone, email)
                    df_full = pd.DataFrame(buyers)

                    preview_rows = []
                    for b in buyers:
                        full_name = (
                            b.get("fullName")
                            or b.get("Full Name")
                            or (
                                f"{(b.get('firstName') or b.get('First Name') or '').strip()} "
                                f"{(b.get('lastName') or b.get('Last Name') or '').strip()}"
                            ).strip()
                        )
                        phone = b.get("Phones_Formatted") or b.get("phone") or b.get("Phones")
                        email = b.get("Email") or b.get("email")

                        preview_rows.append({
                            "Name": full_name,
                            "Phone": phone,
                            "Email": email
                        })

                    df_preview = pd.DataFrame(preview_rows)

                    # 3) Upload the full buyer list to blob storage
                    filename = f"buyers_{city}_{state}_{uuid.uuid4().hex}.xlsx"
                    blob_service = getattr(self.lead_gen_service, "blob_service", None)

                    excel_link = None
                    if blob_service is not None and not df_full.empty:
                        excel_link = blob_service.upload_dataframe(
                            container_name="buyers",
                            file_name=filename,
                            df=df_full
                        )

                    # 4) Create a compact preview of the buyers for the LLM to show inline
                    preview_text = (
                        AzureBlobService.get_dataframe_preview(df_preview)
                        if not df_preview.empty
                        else "No buyer preview available."
                    )

                    if excel_link:
                        context_data = (
                            f"The link to the full list of buyers for {city}, {state} is located here. "
                            f"Link: {excel_link} Here's a preview of up to {len(preview_rows)} buyers "
                            f"(name, phone, email): {preview_text}"
                        )
                    else:
                        context_data = (
                            f"Here is a preview of up to {len(preview_rows)} buyers for {city}, {state} "
                            f"(name, phone, email only): {preview_text} "
                            f"The blob storage link could not be generated, so let the user know results are only shown inline."
                        )

            # Inject context + session memory and then stream the final completion
            request_body = self._add_context_to_request(
                request_body=request_body,
                context_data=context_data,
                system_message=buyers_config.system_message,
                route="Buyers"
            )

            async for chunk in self.openai_service.create_chat_completion(
                messages=request_body["messages"],
                prompt_config=buyers_config
            ):
                yield chunk

        except Exception as e:
            error_context = {
                'service': 'ChatHandler',
                'method': '_handle_buyers_query',
                'prompt': prompt
            }
            await self.discord_reporter.report_error(e, error_context)
            raise


    async def _handle_offtopic_query(self, prompt: str, request_body: Dict) -> AsyncGenerator:
        """OffTopic: preserve filtered history + injected system message with current datetime."""
        try:
            original_messages = request_body.get("messages", [])
            filtered_messages = [msg for msg in original_messages if msg.get("role") != "system"]

            config = self.prompt_configs["OffTopic"]
            current_time = datetime.now().strftime("%B %d, %Y %I:%M %p")
            final_prompt = config.system_message.replace("{{currentDateTime}}", current_time)

            messages = [{"role": "system", "content": final_prompt}] + filtered_messages

            async for chunk in self.openai_service.create_reasoning_chat_completion(
                messages=messages,
                prompt_config=config
            ):
                yield chunk

        except Exception as e:
            error_context = {
                'service': 'ChatHandler',
                'method': '_handle_offtopic_query',
                'prompt': prompt
            }
            await self.discord_reporter.report_error(e, error_context)
            raise

    # ===========================
    # Context utilities
    # ===========================
    def _add_context_to_request(
        self,
        request_body: dict,
        context_data: Any,
        system_message: str,
        route: str = "Default",
        lead_type: str = None
    ) -> dict:
        """
        Merge context into the request instead of replacing it.
        - Keeps a rolling 'session_summary' in request_body
        - Injects a compressed summary of context for continuity
        - Only attaches raw context if needed in this turn
        """
        messages = request_body.get("messages", [])
        session_summary = request_body.get("session_summary", "")

        # Raw context for this turn
        raw_context = self._format_context(context_data)
        # Compressed summary persisted across turns
        compressed = self._compress_context_summary(context_data, route, lead_type)

        if compressed:
            session_summary += f"\n\n[{route} Summary]\n{compressed}"
            request_body["session_summary"] = session_summary.strip()

        # Build messages with budget + session memory
        final_messages = self._build_messages_with_budget(
            route=route,
            system_message=system_message,
            original_messages=messages,
            retrieved_context=raw_context,
            session_summary=session_summary
        )
        request_body["messages"] = final_messages
        return request_body

    def _compress_context_summary(self, context_data: Any, route: str, lead_type: str = None) -> str:
        """Create a compact route-tagged summary that persists across turns."""
        if not context_data:
            return ""

        prefix = f"{route}" + (f" ({lead_type})" if lead_type else "")
        if isinstance(context_data, list):
            sample = []
            for item in context_data[:3]:  # first 3 examples
                if isinstance(item, dict):
                    addr = item.get("address") or item.get("name") or str(item)[:80]
                    sample.append(f"- {addr}")
                else:
                    sample.append(f"- {str(item)[:80]}")
            return f"{prefix}: {len(context_data)} items retrieved. Examples:\n" + "\n".join(sample)

        if isinstance(context_data, dict):
            keys = list(context_data.keys())
            return f"{prefix}: dict with keys {keys[:5]}"

        if isinstance(context_data, str):
            return f"{prefix}: {context_data[:200]}..."

        return f"{prefix}: {str(context_data)[:200]}..."

    def _infer_lead_type_from_url(self, url: str) -> str:
        """Infer lead type from the Zillow query string."""
        if not url:
            return "Unknown"
        if "fixer-upper_att" in url:
            return "Fixer Upper"
        if "/rentals/" in url:
            return "Tired Landlords"
        if '"pf":{"value":true}' in url:
            return "Pre-Foreclosure"
        if '"att":{"value":"as is"}' in url:
            return "As-Is"
        if '"built":{"min":2015}' in url and '"ac":{"value":true}' in url:
            return "Subject To"
        # Heuristic FSBO check; keep broad
        if '"doz":{"value":"36m"}' in url and '"category":"cat2"' in url:
            return "FSBO"
        return "General Lead"

    # ===========================
    # Message formatting helpers
    # ===========================
    def _format_context_block(self, item: dict | str | list, idx: int) -> str:
        """
        Turn one context item into a clean, model-friendly block.
        Supports dicts with common keys: filename/page/text/content/chunk/metadata.
        Avoids bracketed inline citations inside the context itself.
        """
        if isinstance(item, str):
            return f"{idx}. text:\n{item.strip()}"

        filename = (
            (isinstance(item, dict) and item.get("filename"))
            or (isinstance(item, dict) and item.get("file"))
            or (isinstance(item, dict) and (item.get("metadata") or {}).get("filename"))
            or (isinstance(item, dict) and (item.get("meta") or {}).get("filename"))
            or ""
        )
        page = (
            (isinstance(item, dict) and item.get("page"))
            or (isinstance(item, dict) and (item.get("metadata") or {}).get("page"))
            or (isinstance(item, dict) and (item.get("meta") or {}).get("page"))
            or ""
        )
        text = (
            (isinstance(item, dict) and (item.get("text")
                                         or item.get("content")
                                         or item.get("chunk")
                                         or (item.get("metadata") or {}).get("text")
                                         or (item.get("meta") or {}).get("text")))
            or ""
        )

        header_bits = []
        if filename:
            header_bits.append(f"filename: {filename}")
        if page != "":
            header_bits.append(f"page: {page}")

        header = ("; ".join(header_bits)) if header_bits else "context item"
        body = (text or "").strip()

        return f"{idx}. {header}\n{body}"

    def _format_context(self, context_data: Any) -> str:
        """
        Normalize any context_data into a single string for the 'Context:' block.
        - list -> numbered blocks
        - dict -> single block
        - str/other -> stringified
        """
        if isinstance(context_data, list):
            parts = []
            for i, item in enumerate(context_data, start=1):
                parts.append(self._format_context_block(item, i))
            return "\n\n".join(parts)

        if isinstance(context_data, dict):
            return self._format_context_block(context_data, 1)

        return str(context_data)

    # ===========================
    # Token budgeting + builder
    # ===========================
    def _estimate_tokens(self, text: str, model: str = "gpt-4o-mini") -> int:
        if not text:
            return 0
        # ~4 chars/token heuristic
        return max(1, int(len(text) / 4))

    def _score_message(self, msg: dict) -> int:
        """Light importance scoring to keep salient turns."""
        content = (msg.get("content") or "").lower()
        score = 0
        if any(tok in content for tok in ["decide", "decision", "constraint", "deadline", "assume", "assumption"]):
            score += 3
        if any(ch.isdigit() for ch in content):
            score += 2
        if "http://" in content or "https://" in content:
            score += 2
        if any(word in content for word in ["sorry", "correction", "correct", "update", "revised"]):
            score += 2
        if msg.get("role") == "user":
            score += 1
        return score

    def _pick_recent_salient_messages(self, history: list, hard_cap_msgs: int = 8) -> list:
        cleaned = [m for m in history if m.get("role") in ("user", "assistant")]
        indexed = list(enumerate(cleaned))
        scored = []
        for idx, m in indexed:
            score = self._score_message(m) + (idx / max(1, len(cleaned)))
            scored.append((score, idx, m))

        tail = cleaned[-4:]
        tail_ids = {id(m) for m in tail}

        # Top by score, maintain chronological order
        top = sorted(scored, key=lambda x: x[0], reverse=True)[:hard_cap_msgs]
        top_msgs = [m for _, _, m in sorted(top, key=lambda x: x[1])]

        merged = []
        seen = set()
        for m in (top_msgs + tail):
            if id(m) not in seen:
                merged.append(m)
                seen.add(id(m))

        return [m for m in cleaned if m in merged]

    def _summarize_history_inline(self, history: list, max_completion_tokens: int = 500) -> str:
        if not history:
            return ""
        salient = self._pick_recent_salient_messages(history, hard_cap_msgs=8)
        bullets = []
        for m in salient:
            role = m.get("role")
            content = (m.get("content") or "").strip().replace("\n", " ")
            if len(content) > 350:
                content = content[:320].rstrip() + "…"
            bullets.append(f"- {role}: {content}")

        summary = "Session Summary:\n" + "\n".join(bullets)
        while self._estimate_tokens(summary) > max_completion_tokens and len(bullets) > 4:
            bullets.pop(0)
            summary = "Session Summary:\n" + "\n".join(bullets)

        if self._estimate_tokens(summary) > max_completion_tokens:
            summary = summary[: max(100, int(max_completion_tokens * 4))] + "…"
        return summary

    def _build_messages_with_budget(
        self,
        route: str,
        system_message: str,
        original_messages: list,
        retrieved_context: Any = None,
        session_summary: str = ""
    ) -> list:
        budgets = self.ROUTE_BUDGETS.get(route, self.ROUTE_BUDGETS["Default"])
        total_cap = max(3000, budgets["total_cap"])
        reserve = max(600, budgets["reserve"])
        max_for_input = total_cap - reserve

        # Prepare history (exclude system messages)
        history_no_sys = [m for m in (original_messages or []) if m.get("role") != "system"]
        last_user = next((m for m in reversed(history_no_sys) if m.get("role") == "user"), None)
        if not last_user:
            last_user = {"role": "user", "content": ""}

        msgs: List[Dict[str, str]] = [{"role": "system", "content": system_message.strip()}]
        used_tokens = self._estimate_tokens(system_message)

        # 1) Persisted Session Summary (if any)
        if session_summary:
            ss_text = "Session Summary:\n" + session_summary
            if used_tokens + self._estimate_tokens(ss_text) <= max_for_input:
                msgs.append({"role": "user", "content": ss_text})
                used_tokens += self._estimate_tokens(ss_text)

        # 2) Fresh rolling summary from raw history (lightweight)
        inline_summary = self._summarize_history_inline(history_no_sys, max_completion_tokens=budgets["summary"])
        if inline_summary and used_tokens + self._estimate_tokens(inline_summary) <= max_for_input:
            msgs.append({"role": "user", "content": inline_summary})
            used_tokens += self._estimate_tokens(inline_summary)

        # 3) Recent salient turns (verbatim/truncated)
        recent = self._pick_recent_salient_messages(history_no_sys, hard_cap_msgs=8)
        for m in recent:
            txt = (m.get("content") or "").strip()
            if not txt:
                continue
            est = self._estimate_tokens(txt) + 8
            if used_tokens + est > max_for_input or est > budgets["recent"]:
                max_msg_tokens = max(80, int(budgets["recent"] * 0.6))
                if est > max_msg_tokens:
                    truncated = txt[: max(200, max_msg_tokens * 4)] + "…"
                    t_est = self._estimate_tokens(truncated) + 8
                    if used_tokens + t_est <= max_for_input:
                        msgs.append({"role": m.get("role", "user"), "content": truncated})
                        used_tokens += t_est
                # else skip if it doesn't fit
            else:
                msgs.append({"role": m.get("role", "user"), "content": txt})
                used_tokens += est

        # 4) Context block for this turn (optional)
        if retrieved_context is not None:
            ctx_header = "Context:\n"
            ctx_text = str(retrieved_context)
            ctx_est = self._estimate_tokens(ctx_header + ctx_text)
            ctx_budget = budgets["context"]
            if ctx_est > ctx_budget:
                ctx_text = ctx_text[: max(600, ctx_budget * 4)] + "…"
                ctx_est = self._estimate_tokens(ctx_header + ctx_text)
            if used_tokens + ctx_est <= max_for_input:
                msgs.append({"role": "user", "content": f"{ctx_header}{ctx_text}"})
                used_tokens += ctx_est

        # 5) Final question (last user message)
        q_text = (last_user.get("content") or "").strip()
        q_est = self._estimate_tokens(q_text) + 8
        if used_tokens + q_est > max_for_input:
            remain = max_for_input - used_tokens
            if remain > 80:
                trunc = q_text[: max(200, remain * 4)] + "…"
                msgs.append({"role": "user", "content": trunc})
            else:
                msgs.append({"role": "user", "content": q_text[:400] + "…"})
        else:
            msgs.append({"role": "user", "content": q_text})

        return msgs

    # ===========================
    # Misc helpers
    # ===========================
    async def _extract_city_state_from_prompt(self, prompt: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Uses gpt-4o-mini to extract {city, state} from natural language.
        Returns (city, state) or (None, None) if not found.
        """
        user_prompt = f"Extract the city and state from: {prompt}"

        cfg = self.prompt_configs["CityStateExtraction"]
        # Build a synthetic 'history' using just this user prompt
        async for response in self.openai_service.create_chat_completion(
            messages=[
                {"role": "system", "content": cfg.system_message},
                {"role": "user", "content": user_prompt}
            ],
            prompt_config=cfg
        ):
            raw = response.choices[0].message.content
            break

        # Parse JSON
        try:
            data = json.loads(raw)
            city = data.get("city", "").strip()
            state = data.get("state", "").strip().upper()

            if city and state:
                return city, state
            return None, None
        except Exception as e:
            logging.error(f"[extract_city_state] Failed to parse JSON: {e} — Raw: {raw}")
            return None, None

    async def get_city_state(self, prompt: str) -> Tuple[Optional[str], Optional[str]]:
        """Public wrapper for city/state extraction (useful for tool calls)."""
        return await self._extract_city_state_from_prompt(prompt)

    async def _expand_contract_prompt(self, original_prompt: str) -> str:
        try:
            cfg = self.prompt_configs["ContractsExpansion"]
            # Build a synthetic 'history' using just this user prompt
            history = [{"role": "user", "content": original_prompt}]
            messages = self._build_messages_with_budget(
                route="Contracts",
                system_message=cfg.system_message,
                original_messages=history,
                retrieved_context=None
            )
            async for response in self.openai_service.create_chat_completion(
                messages=messages,
                prompt_config=cfg
            ):
                return response.choices[0].message.content.strip()
        except Exception as e:
            error_context = {
                'service': 'ChatHandler',
                'method': '_expand_contract_prompt',
                'prompt': original_prompt
            }
            await self.discord_reporter.report_error(e, error_context)
            raise

    async def expand_contract_prompt(self, prompt: str) -> str:
        """Public wrapper for contract prompt expansion (useful for tool calls)."""
        return await self._expand_contract_prompt(prompt)

    def _is_url(self, text: str) -> bool:
        if not isinstance(text, str):
            return False
        return text.startswith("http://") or text.startswith("https://")
    
    async def get_address(self, prompt: str) -> str:
        """
        Extract a single US mailing address from a user's prompt.
        Uses your 'mini' (Classification deployment) first, then falls back to regex.
        Returns: full_address (string)
        Raises: ValueError if none found
        """

        system_msg = (
            "You extract a single US property mailing address from user text.\n"
            "Return ONLY valid JSON with this schema:\n"
            '{ "address": "<full address or empty string>" }\n'
            "Rules:\n"
            "- Prefer full address with street, city, state, zip.\n"
            "- If multiple addresses exist, return the most relevant for property comps.\n"
            "- If no address is found, return {\"address\": \"\"}.\n"
            "- Do not include any extra keys."
        )

        try:
            # This assumes you have an Azure OpenAI client like:
            # self.client.chat.completions.create(...)
            # If your method name differs, swap it with your existing call wrapper.
            async for response in self.openai_service.create_chat_completion(
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt},
                ],
                prompt_config=self.prompt_configs['Classification']
            ):
                content = response.choices[0].message.content.strip()

                # sometimes models wrap JSON in ```json fences
                content = re.sub(r"^```json\s*|\s*```$", "", content, flags=re.IGNORECASE).strip()

                data = json.loads(content)
                address = (data.get("address") or "").strip()

                if address:
                    return address

        except Exception:
            # swallow and fallback to regex below
            pass

        # ---- 2) Regex fallback ----
        # This catches common formats like:
        # "123 Main St, San Antonio, TX 78205"
        # "123 Main St San Antonio TX 78205"
        addr_regex = re.compile(
            r"(?P<addr>\b\d{1,6}\s+[A-Za-z0-9#.\-'\s]+?\s+"
            r"(?:Ave|Avenue|St|Street|Rd|Road|Blvd|Boulevard|Ln|Lane|Dr|Drive|Ct|Court|Cir|Circle|Pl|Place|Way|Pkwy|Parkway|Ter|Terrace)\b"
            r"(?:\s*(?:#|Unit|Apt|Suite)\s*[A-Za-z0-9\-]+)?"
            r"(?:\s*,?\s*[A-Za-z.\-'\s]+)?\s*,?\s*[A-Z]{2}\s+\d{5}(?:-\d{4})?\b)",
            re.IGNORECASE,
        )

        m = addr_regex.search(prompt)
        if m:
            return m.group("addr").strip()

        raise ValueError("No address found in prompt. Please include a full address (street, city, state, zip).")
