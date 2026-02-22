import { useRef, useState, useEffect, useContext, useLayoutEffect, useCallback } from "react";
import { CommandBarButton, IconButton, Dialog, DialogType, Stack } from "@fluentui/react";
import { SquareRegular, ShieldLockRegular, ErrorCircleRegular } from "@fluentui/react-icons";

import ReactMarkdown from "react-markdown";
import { Pluggable } from 'unified';
import remarkGfm from 'remark-gfm'
import rehypeRaw from "rehype-raw";
import uuid from 'react-uuid';
import { invert, isEmpty } from "lodash-es";
import DOMPurify from 'dompurify';

import styles from "./Chat.module.css";
// import uc_ai_icon from "../../assets/ARI-Dark--mode.png";
import uc_ai_icon from "../../assets/ari_logo_new.png";
import { XSSAllowTags } from "../../constants/xssAllowTags";
import profile_icon from "../../assets/profile_icon.png";
import collapse_icon from "../../assets/collapse_menu.png";

import {
    ChatMessage,
    ConversationRequest,
    conversationApi,
    Citation,
    ToolMessageContent,
    ChatResponse,
    getUserInfo,
    Conversation,
    historyUpdate,
    historyClear,
    ChatHistoryLoadingState,
    CosmosDBStatus,
    ErrorMessage
} from "../../api";
import { Answer } from "../../components/Answer";
import { QuestionInput } from "../../components/QuestionInput";
import { ChatHistoryPanel } from "../../components/ChatHistory/ChatHistoryPanel";
import { AppStateContext } from "../../state/AppProvider";
import { useBoolean } from "@fluentui/react-hooks";
import { useChatStreamHandler } from '../../hooks/useChatStreamHandler';

const enum messageStatus {
    NotRunning = "Not Running",
    Processing = "Processing",
    Done = "Done"
}

const plugins = [remarkGfm] as const;



const Chat = () => {
    const appStateContext = useContext(AppStateContext)
    const ui = appStateContext?.state.frontendSettings?.ui;
    const AUTH_ENABLED = false;
    const chatMessageStreamEnd = useRef<HTMLDivElement | null>(null);
    const [isLoading, setIsLoading] = useState<boolean>(false);
    const [showLoadingMessage, setShowLoadingMessage] = useState<boolean>(false);
    const [activeCitation, setActiveCitation] = useState<Citation>();
    const [isCitationPanelOpen, setIsCitationPanelOpen] = useState<boolean>(false);
    const abortFuncs = useRef([] as AbortController[]);
    const [showAuthMessage, setShowAuthMessage] = useState<boolean>(false);
    // const [messages, setMessages] = useState<ChatMessage[]>([])
    const [processMessages, setProcessMessages] = useState<messageStatus>(messageStatus.NotRunning);
    const [clearingChat, setClearingChat] = useState<boolean>(false);
    const [hideErrorDialog, { toggle: toggleErrorDialog }] = useBoolean(true);
    const [errorMsg, setErrorMsg] = useState<ErrorMessage | null>()
    const [isTypewriterActive, setIsTypewriterActive] = useState<boolean>(false);
    // const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
    const [isMenuOpen, setIsMenuOpen] = useState(false);
    const [shouldStopTyping, setShouldStopTyping] = useState(false);
    const [defaultQuestion, setDefaultQuestion] = useState<string | undefined>();
    const chatMessageStreamRef = useRef<HTMLDivElement | null>(null);
    const userHasScrolledRef = useRef(false);
    const lastScrollTimeRef = useRef<number>(0);
    const scrollCooldownMs = 100;

    const prevRef = useRef({
        showLoadingMessage: false,
        processMessages: messageStatus.NotRunning,
        messages: [] as ChatMessage[]
    });

    //---------------------------------DYNAMICALLY ADJUST TO MOBILE VIEW--------------------------------//

    const [isMobile, setIsMobile] = useState<boolean>(false);

    useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < 1326);
    checkMobile();
    window.addEventListener("resize", checkMobile);
    return () => window.removeEventListener("resize", checkMobile);
    }, []);

    //---------------------------------ADD PROFILE MENU--------------------------------//

    const {
        messages,
        setMessages,
        processResultMessage,
        resetStreamBuffer,
        stopStreaming
    } = useChatStreamHandler();

    // ADD THIS RIGHT AFTER:
    // useEffect(() => {
    //     // console.log('🔥 CHAT: Main messages array updated, count:', messages.length);
    //     messages.forEach((msg, index) => {
    //         console.log(`📝 CHAT Message ${index}:`, {
    //             id: msg.id,
    //             role: msg.role,
    //             contentLength: msg.content?.length || 0,
    //             contentPreview: msg.content?.slice(0, 50) + '...'
    //         });
    //     });
    // }, [messages]);

    const errorDialogContentProps = {
        type: DialogType.close,
        title: errorMsg?.title,
        closeButtonAriaLabel: 'Close',
        subText: errorMsg?.subtitle,
    };

    const modalProps = {
        titleAriaId: 'labelId',
        subtitleAriaId: 'subTextId',
        isBlocking: true,
        styles: { main: { maxWidth: 450 } },
    }

    const [ASSISTANT, TOOL, ERROR] = ["assistant", "tool", "error"]

    useEffect(() => {
        if (appStateContext?.state.isCosmosDBAvailable?.status !== CosmosDBStatus.Working  
            && appStateContext?.state.isCosmosDBAvailable?.status !== CosmosDBStatus.NotConfigured
            && appStateContext?.state.chatHistoryLoadingState === ChatHistoryLoadingState.Fail 
            && hideErrorDialog) {
            let subtitle = `${appStateContext.state.isCosmosDBAvailable.status}. Please contact the site administrator.`
            setErrorMsg({
                title: "Chat history is not enabled",
                subtitle: subtitle
            })
            toggleErrorDialog();
        }
    }, [appStateContext?.state.isCosmosDBAvailable]);

    const handleErrorDialogClose = () => {
        toggleErrorDialog()
        setTimeout(() => {
            setErrorMsg(null)
        }, 500);
    }

    const [userName, setUserName] = useState<string>("");
    const [userEmail, setUserEmail] = useState<string>("");
    const [subscriptionPlan, setSubscriptionPlan] = useState<string>("");
    const [subscriptionId, setSubscriptionId] = useState<string>("");

    // Set the username in the profile menu 
    useEffect(() => {
        fetch("/api/userinfo", { credentials: "include" })
            .then((res) => res.json())
            .then((data) => {
            setUserName(data.name || "User");
            setUserEmail(data.email || "");
            setSubscriptionPlan(data.subscription_plan || "");
            setSubscriptionId(data.subscription_id || "");
            //console.log("Fetched user info:", data);
            })
            .catch(() => {
            setUserName("User");
            setUserEmail("");
            setSubscriptionPlan("");
            setSubscriptionId("");
            });
        }, []);


    
    // Detect user's scroll action
    useEffect(() => {
        const container = chatMessageStreamRef.current;
        if (!container) {
            console.log("No container found");
            return;
        }
    
        const handleWheel = () => {
            userHasScrolledRef.current = true;
        };
    
        container.addEventListener('wheel', handleWheel, { passive: true });
    
        return () => {
            container.removeEventListener('wheel', handleWheel);
        };
    }, [chatMessageStreamRef.current]);
    
    useEffect(() => {
        console.log('Typewriter active state changed:', isTypewriterActive);
    }, [isTypewriterActive]);

    useEffect(() => {
        setIsLoading(appStateContext?.state.chatHistoryLoadingState === ChatHistoryLoadingState.Loading)
    }, [appStateContext?.state.chatHistoryLoadingState])


    const getUserInfoList = async () => {
        if (!AUTH_ENABLED) {
            setShowAuthMessage(false);
            return;
        }
        const userInfoList = await getUserInfo();
        if (userInfoList.length === 0 && window.location.hostname !== "127.0.0.1") {
            setShowAuthMessage(false);
        }
        else {
            setShowAuthMessage(false);
        }
    }    
     
    
    const cleanupAfterRequest = (abortController: AbortController) => {
        console.log('Cleaning up request');
        abortFuncs.current = abortFuncs.current.filter((a) => a !== abortController);

        if (!isTypewriterActive) {
            setProcessMessages(messageStatus.Done);
        }

        // resetStreamBuffer(); // Reset the stream buffer here too
        scrollToBottom(); 
    };

    const handleExternalLink = (url: string) => {
        window.open(url, "_blank");
    };

    const handleSetPrompt = (prompt: string) => {
        setDefaultQuestion(undefined); // Temporarily clear the state
        setTimeout(() => setDefaultQuestion(prompt), 0); // Reapply the prompt after a delay
    };
    
    const handleCustomAction = () => {
        // Add your custom functionality here
    };
    

    const makeApiRequestWithCosmosDB = async (question: string, conversationId?: string) => {
        setShouldStopTyping(false); 
        setIsLoading(true);
        setShowLoadingMessage(true);
        setIsTypewriterActive(true);
        userHasScrolledRef.current = false; 
    
        const abortController = new AbortController();
        abortFuncs.current.unshift(abortController);
    
        const userMessage: ChatMessage = {
            id: uuid(),
            role: "user",
            content: question,
            date: new Date().toISOString(),
        };
    
        // Initialize or Update Conversation
        let conversation: Conversation | null | undefined;
        if (!conversationId) {
            conversation = {
                id: uuid(),
                title: question,
                messages: [userMessage], // Start new conversation
                date: new Date().toISOString(),
            };
        } else {
            conversation = appStateContext?.state?.chatHistory?.find((conv) => conv.id === conversationId);
            if (conversation) {
                // Check if message with same content and timestamp already exists
                const isDuplicate = conversation.messages.some(msg => 
                    msg.role === userMessage.role && 
                    msg.content === userMessage.content &&
                    Math.abs(new Date(msg.date).getTime() - new Date(userMessage.date).getTime()) < 1000
                );
                
                if (!isDuplicate) {
                    conversation.messages.push(userMessage);
                } else {
                    console.log("Prevented duplicate message:", userMessage);
                }
            } else {
                console.error("Conversation not found.");
                cleanupAfterRequest(abortController);
                return;
            }
        }
        
        // Dispatch Current Chat and Preserve State
        appStateContext?.dispatch({ type: "UPDATE_CURRENT_CHAT", payload: conversation });

        // console.log('👤 CHAT: Adding user message:', userMessage.id);
        setMessages((prevMessages) => {
            // console.log('👤 CHAT: Before adding user - count:', prevMessages.length);
            const newMessages = [...prevMessages, userMessage];
            // console.log('👤 CHAT: After adding user - count:', newMessages.length);
            return newMessages;
        }); 
    
        const request: ConversationRequest = {
            messages: conversation.messages.filter((msg) => msg.role !== ERROR),
            conversation_id: conversationId, // Include conversation_id if available
        };
    
        try {
            // Use WebSocket for Streaming
            resetStreamBuffer();
            await conversationApi(
                request,
                (message) => {
                    const result: ChatResponse = typeof message === "string" ? JSON.parse(message) : message;
    
                    if (result.choices?.length > 0) {
                        result.choices[0].messages.forEach((msg) => {
                            msg.id = userMessage.id; 
                            //msg.id = uuid();
                            msg.date = new Date().toISOString();
                            processResultMessage(msg, userMessage, conversationId); // Process streamed message
                        });
    
                        if (result.choices[0].messages.some((msg) => msg.role === ASSISTANT)) {
                            // scrollToBottom();
                            setShowLoadingMessage(false); // Stop loading when assistant responds
                        }
                    }
                },
                abortController.signal,
                '/ws/history/generate' // Specify the new WebSocket endpoint
            );
        } catch (error: unknown) {
            // Check if error is an Error object and if it's an abort
            if (error instanceof Error && error.name === 'AbortError') {
                return; // Exit silently for aborted requests
            }
        
            // Only show error for non-abort errors
            console.error("Error:", error);
            const errorMessageObj: ChatMessage = {
                id: uuid(),
                role: ERROR,
                content: "Real Estate must be booming because we're experiencing heavy loads and the geniuses at REI Labs are on it. Please email info@reilabs.ai for additional support.",
                date: new Date().toISOString(),
            };
            conversation.messages.push(errorMessageObj);
            appStateContext?.dispatch({ type: "UPDATE_CURRENT_CHAT", payload: conversation });
            stopGenerating();
        } finally {
            cleanupAfterRequest(abortController);
        }
    };

    const clearChat = async () => {
        setClearingChat(true);
        if (appStateContext?.state.currentChat?.id && appStateContext?.state.isCosmosDBAvailable.cosmosDB) {
            try {
                await historyClear(appStateContext?.state.currentChat.id);
            } catch (error) {
                 console.error("Error clearing chat:", error);
            } finally {
                // Batch all state updates
                appStateContext.dispatch({
                    type: 'CLEAR_CHAT',
                    payload: {
                        chatId: appStateContext.state.currentChat.id,
                        chat: appStateContext.state.currentChat
                    }
                });
                // Reset local state
                setActiveCitation(undefined);
                setIsCitationPanelOpen(false);
                setMessages([]);
                resetStreamBuffer(); // Ensure stream buffer is cleared
            }
        }
        setClearingChat(false);
    };

    const newChat = () => {
        setProcessMessages(messageStatus.Processing)
        setMessages([])
        setIsCitationPanelOpen(false);
        setActiveCitation(undefined);
        appStateContext?.dispatch({ type: 'UPDATE_CURRENT_CHAT', payload: null });
        setProcessMessages(messageStatus.Done)
    };

    const stopGenerating = () => {
        setShouldStopTyping(true);
        abortFuncs.current.forEach(a => a.abort());
        setShowLoadingMessage(false);
        setIsLoading(false);
        setIsTypewriterActive(false);
        resetStreamBuffer();
        stopStreaming();

        // Add assistant "stop" message
        const stopMsg: ChatMessage = {
            id: uuid(),
            role: "assistant",
            content: "⚠️ Analysis interrupted - Ready when you are.",
            date: new Date().toISOString()
        };

        setMessages(prev => [...prev, stopMsg]);
    };

    // useEffect(() => {
    //     console.log('🔄 CHAT: Syncing with currentChat:', {
    //         hasCurrentChat: !!appStateContext?.state.currentChat,
    //         currentChatId: appStateContext?.state.currentChat?.id,
    //         currentChatMessageCount: appStateContext?.state.currentChat?.messages?.length || 0,
    //         isCurrentlyStreaming: isTypewriterActive || isLoading
    //     });
        
    //     // Don't sync if we're currently streaming - let the stream handler manage messages
    //     if (isTypewriterActive || isLoading) {
    //         console.log('⏸️ CHAT: Skipping sync - currently streaming');
    //         return;
    //     }
        
    //     if (appStateContext?.state.currentChat) {
    //         console.log('📥 CHAT: Setting messages from currentChat, count:', appStateContext.state.currentChat.messages.length);
    //         setMessages(appStateContext.state.currentChat.messages)
    //     } else {
    //         console.log('🗑️ CHAT: Clearing messages (no currentChat)');
    //         setMessages([])
    //     }
    // }, [appStateContext?.state.currentChat, isTypewriterActive, isLoading]);

    useLayoutEffect(() => {
        const saveToDB = async (messages: ChatMessage[], id: string) => {
            const response = await historyUpdate(messages, id)
            return response
        }

        if (appStateContext && appStateContext.state.currentChat && processMessages === messageStatus.Done) {
            if (appStateContext.state.isCosmosDBAvailable.cosmosDB) {
                if (!appStateContext?.state.currentChat?.messages) {
                    console.error("Failure fetching current chat state.");
                    return;
                }
        
                saveToDB(appStateContext.state.currentChat.messages, appStateContext.state.currentChat.id)
                    .then((res) => {
                        if (!res.ok) {
                            // let errorMessage = "An error occurred. Answers can't be saved at this time. If the problem persists, please contact the site administrator.";
                            let errorChatMsg: ChatMessage = {
                                id: uuid(),
                                role: ERROR,
                                content: "Real Estate must be booming because we're experiencing heavy loads and the geniuses at REI Labs are on it. Please email info@reilabs.ai for additional support.",
                                date: new Date().toISOString(),
                            };
        
                            if (!appStateContext?.state.currentChat?.messages) {
                                throw new Error("Failure fetching current chat state.");
                            }
        
                            // Merge error message with current state
                            setMessages((prevMessages) => [
                                ...prevMessages,
                                errorChatMsg,
                            ]);
                        }
                        return res as Response;
                    })
                    .catch((err) => {
                        console.error("Error: ", err);
        
                        let errRes: Response = {
                            ...new Response(),
                            ok: false,
                            status: 500,
                        };
        
                        // Optionally handle additional error scenarios
                        return errRes;
                    });
            }
        
            // Safely update the chat history and messages
            appStateContext?.dispatch({
                type: "UPDATE_CHAT_HISTORY",
                payload: appStateContext.state.currentChat,
            });
        
            // Append new messages rather than overwriting
            setMessages((prevMessages) => {
                const currentMessages = appStateContext?.state.currentChat?.messages || [];
            
                // Use message `id` to filter out duplicates
                const newMessages = currentMessages.filter(
                    (msg) => !prevMessages.some((prev) => prev.id === msg.id)
                );
            
                // You could also check based on `content` if necessary:
                // const newMessages = currentMessages.filter(
                //     (msg) => !prevMessages.some((prev) => prev.content === msg.content)
                // );
            
                return [...prevMessages, ...newMessages];
            });
            

        
            // Reset processMessages after ensuring messages are safe
            setProcessMessages(messageStatus.NotRunning);
        }
        
    }, [processMessages]);

    useEffect(() => {
        if (AUTH_ENABLED !== undefined) getUserInfoList();
    }, [AUTH_ENABLED]);

    useLayoutEffect(() => {
        scrollToBottom();
    }, [showLoadingMessage]);

    const scrollToBottom = useCallback(() => {
        const now = Date.now();
        if (now - lastScrollTimeRef.current < scrollCooldownMs) {
            return;
        }
    
        if (chatMessageStreamEnd.current && !userHasScrolledRef.current) {
            lastScrollTimeRef.current = now;
            chatMessageStreamEnd.current.scrollIntoView({ 
                behavior: "smooth",
                block: "end"
            });
        }
    }, []);

    const onShowCitation = (citation: Citation) => {
        setActiveCitation(citation);
        setIsCitationPanelOpen(true);
    };

    const onViewSource = (citation: Citation) => {
        if (citation.url && !citation.url.includes("blob.core")) {
            window.open(citation.url, "_blank");
        }
    };

    const parseCitationFromMessage = (message: ChatMessage) => {
        if (message?.role && message?.role === "tool") {
            try {
                const toolMessage = JSON.parse(message.content) as ToolMessageContent;
                return toolMessage.citations;
            }
            catch {
                return [];
            }
        }
        return [];
    }

    const disabledButton = () => {
        return isLoading || (messages && messages.length === 0) || clearingChat || appStateContext?.state.chatHistoryLoadingState === ChatHistoryLoadingState.Loading
    }

   //----------------------ADD PROFILE MENU----------------------------------//

    const ProfileMenu = () => {
        const [isOpen, setIsOpen] = useState(false);
        const menuRef = useRef<HTMLDivElement | null>(null);
    
        useEffect(() => {
            const handleClickOutside = (e: MouseEvent) => {
                if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
                    setIsOpen(false);
                }
            };
    
            document.addEventListener("mousedown", handleClickOutside);
            return () => document.removeEventListener("mousedown", handleClickOutside);
        }, []);
    
        return (
            <div ref={menuRef} className={styles.profileWrapper}>
                <img
                    src={profile_icon}
                    alt="Profile"
                    onClick={() => setIsOpen(!isOpen)}
                    className={styles.profileIcon}
                    aria-hidden="true"
                />
                {isOpen && (
                    <div className={styles.dropdownMenu}>
                        {/* <button className={styles.welcomeUsername} disabled role="presentation">
                        {userName ? `Welcome ${userName}!` : "Welcome!"}
                             </button>
                        <hr className={styles.dropdownDivider} /> */}
                        
                        <div className={styles.userInfo}>
                                {/* <strong>{userEmail}</strong> */}
                                <div className={styles.userEmail}>{userEmail}</div>
                                {/* <p>{userEmail}</p> */}
                                {/* <p>Plan: {subscriptionPlan}</p> */}
                                <button className={styles.upgradeButton} onClick={() => window.location.href = "https://reilabs.ai/my-account"}>
                                    Upgrade Plan
                                    </button>
                                </div>
                        <hr className={styles.dropdownDivider} />

                        <button onClick={() => window.location.href = "https://reilabs.ai/my-account"}>Dashboard</button>
                        <button onClick={() => window.location.href = "/logout"}>Logout</button>
                        <hr className={styles.dropdownDivider} />
                        

                        <a href="https://reilabs.ai/privacy-policy/" target="_blank" rel="noopener noreferrer" className={styles.dropdownLink}>
                                Privacy Policy
                            </a>
                            <a href="https://reilabs.ai/terms-of-service/" target="_blank" rel="noopener noreferrer" className={styles.dropdownLink}>
                                Terms & Conditions
                            </a>
                            <a href="https://reilabs.ai/disclaimer/" target="_blank" rel="noopener noreferrer" className={styles.dropdownLink}>
                                Disclaimer
                            </a>
                    </div>
                )}
            </div>
        );
    };

    //----------------------ADD PROFILE MENU----------------------------------//

    const [isRightMenuCollapsed, setIsRightMenuCollapsed] = useState(false);

    return (
        <div className={styles.container} role="main">
            {/* Mobile Menu */}
            {isMobile && (
                <>
                <ProfileMenu />
                <button
                    className={styles.hamburgerButton}
                    onClick={() => setIsMenuOpen(!isMenuOpen)}
                >
                    ☰ Menu
                </button>

                {isMenuOpen && (
                    <div className={`${styles.mobileMenu} ${
                                isMenuOpen ? '' : styles.hidden
                            }`}
                        >
                        <button
                            className={styles.closeButton}
                            onClick={() => setIsMenuOpen(false)}
                        >
                            ✖ Close
                        </button>
                        
                        {/* <div className={styles.section}>
                            <h3>Strategies</h3>
                            <ul>
                                <li><button>Wholesaling</button></li>
                                <li><button disabled>Wholetailing</button></li>
                                <li><button disabled>Novations</button></li>
                                <li><button disabled>Equity Listing</button></li>
                                <li><button disabled>Net Sale Listing</button></li>
                                <li><button disabled>Fix & Flip</button></li>
                                <li><button>Subject To</button></li>
                                <li><button disabled>Lease Options</button></li>
                                <li><button disabled>Creative Financing</button></li>
                                <li><button disabled>Entitlements</button></li>
                                <li><button disabled>Development</button></li>
                                <li><button disabled>Multi-Family</button></li>
                                <li><button disabled>Commercial</button></li>
                                <li><button disabled>RV/Mobile Homes</button></li>
                                <li><button disabled>Motels</button></li>
                                <li><button disabled>Land</button></li>
                                <li><button disabled>Subdividing Land</button></li>
                                <li><button disabled>Lic. Real Estate</button></li>
                                <li><button disabled>Oil & Gas</button></li>
                            </ul>
                        </div> */}

                        {/* <div className={styles.section}>
                            <h3>Mentors</h3>
                            <ul>
                                <li><button disabled>Mentor TBD</button></li>
                                <li><button disabled>Mentor TBD</button></li>
                                <li><button disabled>Mentor TBD</button></li>
                                <li><button disabled>Mentor TBD</button></li>
                            </ul>
                        </div> */}
                        <div className={styles.section}>
                             <h3>REI Tools & Data</h3>
                                <ul>
                                    <li><button onClick={() => window.open("https://trial.propstreampro.com/hbhs/", "_blank")} >Propstream</button></li>
                                    {/* <li><button onClick={() => window.open("https://ari.aispeakly.com/", "_blank")} >AI Sales Training</button></li> */}
                                    <li><button onClick={() => window.open("https://ari.uprankpro.com/", "_blank")} >AI Marketing</button></li>
                                    {/* <li><button onClick={() => window.open("https://chatarv.ai?fpr=reilabs", "_blank")} >ChatARV</button></li>
                                    <li><button onClick={() => window.open("https://leads.reilabs.ai/", "_blank")} >Tax-Lien Leads</button></li>
                                    <li><button onClick={() => window.open("https://app.closebot.com/a?fpr=reilabs", "_blank")} >CloseBot</button></li> */}
                                    {/* <li><button disabled>Brokerless</button></li> */}
                                </ul>
                        </div>

                        {/* <div className={styles.section}>
                            <h3>Professional Services</h3>
                            <ul>
                            <li><button disabled onClick={() =>
                                        handleSetPrompt(
                                        "Can I have a list of real estate attorneys in <CITY, STATE>"
                                        )
                                    }>Attorneys</button></li>
                                <li><button disabled>Title Companies</button></li>
                                <li><button disabled>HM Lenders</button></li>
                                <li><button disabled>PM Lenders</button></li>
                                <li><button disabled>Note Buyers</button></li>
                            </ul>
                        </div> */}

                        <div className={styles.section}>
                            <h3>REI Events</h3>
                            <ul>
                               
                                <li>
                                    <button onClick={() => window.open("https://wholesalinglive.com/", "_blank")}>
                                        WSL 2025
                                    </button>
                                    </li>
                            </ul>
                        </div>
                    </div>
                )}
                </>
            )}

            {/* Desktop Left Menu */}
            {!isMobile && (
                <div className={styles.leftMenu}>
                {/* <div className={styles.section}>
                    <h3>Strategies</h3>
                    <ul>
                        <li><button>Wholesaling</button></li>
                        <li><button disabled>Wholetailing</button></li>
                        <li><button disabled>Novations</button></li>
                        <li><button disabled>Equity Listing</button></li>
                        <li><button disabled>Net Sale Listing</button></li>
                        <li><button disabled>Fix & Flip</button></li>
                        <li><button>Subject To</button></li>
                        <li><button disabled>Lease Options</button></li>
                        <li><button disabled>Creative Financing</button></li>
                        <li><button disabled>Entitlements</button></li>
                        <li><button disabled>Development</button></li>
                        <li><button disabled>Multi-Family</button></li>
                        <li><button disabled>Commercial</button></li>
                        <li><button disabled>RV/Mobile Homes</button></li>
                        <li><button disabled>Motels</button></li>
                        <li><button disabled>Land</button></li>
                        <li><button disabled>Subdividing Land</button></li>
                        <li><button disabled>Lic. Real Estate</button></li>
                        <li><button disabled>Oil & Gas</button></li>
                    </ul>
                </div> */}

                {/* <div className={styles.section}>
                    <h3>Data</h3>
                    <ul>
                        <li><button disabled>Live Public Data</button></li>
                        <li><button disabled>Live Online Leads</button></li>
                        <li><button disabled>Live Online Buyers</button></li>
                    </ul>
                </div> */}
            </div>
            )}
            {/* MAIN CHAT CONTENT */}
            {showAuthMessage ? (
                <Stack className={styles.chatEmptyState}>
                    <ShieldLockRegular className={styles.chatIcon} style={{ color: 'darkorange', height: "200px", width: "200px" }} />
                    <h1 className={styles.chatEmptyStateTitle}>Authentication Not Configured</h1>
                    <h2 className={styles.chatEmptyStateSubtitle}>
                        This app does not have authentication configured. Please add an identity provider by finding your app in the <a href="https://portal.azure.com/" target="_blank">Azure Portal</a> 
                        and following <a href="https://learn.microsoft.com/en-us/azure/app-service/scenario-secure-app-authentication-app-service#3-configure-authentication-and-authorization" target="_blank">these instructions</a>.
                    </h2>
                    <h2 className={styles.chatEmptyStateSubtitle} style={{ fontSize: "20px" }}><strong>Authentication configuration takes a few minutes to apply. </strong></h2>
                    <h2 className={styles.chatEmptyStateSubtitle} style={{ fontSize: "20px" }}><strong>If you deployed in the last 10 minutes, please wait and reload the page after 10 minutes.</strong></h2>
                </Stack>
            ) : (
                <Stack horizontal className={styles.chatRoot}>
                    <div className={styles.chatContainer}>

                        {!messages || messages.length < 1 ? (
                            <Stack className={styles.chatEmptyState}>
                                <img
                                    src={uc_ai_icon}
                                    className={styles.chatIcon}
                                    aria-hidden="true"
                                />
                                {/* <h1 className={styles.chatEmptyStateTitle}>{ui?.chat_title}</h1>*/
                                <h2 className={styles.chatEmptyStateSubtitle}>{ui?.version}</h2> }
                            </Stack>
                        ) : (
                            <div className={styles.chatMessageStream} ref={chatMessageStreamRef} style={{ marginBottom: isLoading ? "40px" : "0px" }} role="log">
                               <div className={styles.chatInnerStream}> {/* Add and inner class to handle the scroll*/}
                                {messages.map((answer, index) => (
                                    <div key={answer.id || index}> {/* Use `answer.id` or fallback to `index` */}
                                        {answer.role === "user" ? (
                                            <div className={styles.chatMessageUser} tabIndex={0}>
                                                <div className={styles.chatMessageUserMessage}>{answer.content}</div>
                                            </div>
                                        ) : answer.role === "assistant" ? (
                                            <div className={styles.chatMessageGpt}>
                                                <Answer
                                                    answer={{
                                                        answer: answer.content,
                                                        citations: parseCitationFromMessage(messages[index - 1]),
                                                        message_id: answer.id,
                                                        feedback: answer.feedback,
                                                    }}
                                                    onCitationClicked={c => onShowCitation(c)}
                                                    onStreamingComplete={() => {
                                                        setIsTypewriterActive(false);
                                                        setIsLoading(false);
                                                        setShowLoadingMessage(false);
                                                        setProcessMessages(messageStatus.Done); // Move this here
                                                    }}
                                                    shouldStop={shouldStopTyping}
                                                    scrollToBottom={scrollToBottom}
                                                />
                                            </div>
                                        ) : answer.role === ERROR ? (
                                            <div className={styles.chatMessageError}>
                                                {/* <Stack horizontal className={styles.chatMessageErrorContent}>
                                                    <ErrorCircleRegular className={styles.errorIcon} style={{ color: "rgba(182, 52, 67, 1)" }} />
                                                    <span>Error</span>
                                                </Stack> */}
                                                <span className={styles.chatMessageErrorContent}>{answer.content}</span>
                                            </div>
                                        ) : null}
                                        
                                    </div>
                                    
                                ))}

                                {showLoadingMessage && (
                                    <>
                                        <div className={styles.chatMessageGpt}>
                                            <Answer
                                                answer={{
                                                    answer: "Generating answer...",
                                                    citations: []
                                                }}
                                                onCitationClicked={() => null}
                                            />
                                        </div>
                                    </>
                                )}
                                <div ref={chatMessageStreamEnd} />
                                </div>
                            </div>
                        )}

                        <Stack horizontal className={styles.chatInput}>
                            {(isLoading || isTypewriterActive) && (
                                <Stack
                                    horizontal
                                    className={styles.stopGeneratingContainer}
                                    role="button"
                                    aria-label="Stop generating"
                                    tabIndex={0}
                                    onClick={stopGenerating}
                                    onKeyDown={e => e.key === "Enter" || e.key === " " ? stopGenerating() : null}
                                >
                                    <SquareRegular className={styles.stopGeneratingIcon} aria-hidden="true" />
                                    <span className={styles.stopGeneratingText} aria-hidden="true">Stop generating</span>
                                </Stack>
                            )}
                            <Stack>
                            {appStateContext?.state.isCosmosDBAvailable?.status !== CosmosDBStatus.NotConfigured && (
                                <CommandBarButton
                                    role="button"
                                    styles={{
                                        icon: {
                                            color: '#d9c984',
                                            ':hover': {
                                                color: '#c5b269' // Darker gold on hover
                                            }
                                        },
                                        iconDisabled: {
                                            color: "#757575 !important" // Darker gray for disabled
                                        },
                                        root: {
                                            color: '#d9c984',
                                            background: "#1a1a1a", // Darker background
                                            ':hover': {
                                                background: "#2d2d2d" // Hover state
                                            }
                                        },
                                        rootDisabled: {
                                            background: "#333333 !important", // Dark disabled background
                                            cursor: "not-allowed"
                                        }
                                    }}
                                    className={styles.newChatIcon}
                                    iconProps={{ iconName: 'Add' }}
                                    onClick={newChat}
                                    disabled={disabledButton()}
                                    aria-label="start a new chat button"
                                />
                            )}

                            <CommandBarButton
                                role="button"
                                styles={{
                                    icon: {
                                        color: '#d9c984',
                                        ':hover': {
                                            color: '#c5b269' // Consistent hover state
                                        }
                                    },
                                    iconDisabled: {
                                        color: "#757575 !important" // Matching disabled color
                                    },
                                    root: {
                                        color: '#d9c984',
                                        background: "#1a1a1a", // Consistent dark background
                                        ':hover': {
                                            background: "#2d2d2d"
                                        }
                                    },
                                    rootDisabled: {
                                        background: "#333333 !important",
                                        cursor: "not-allowed"
                                    }
                                }}
                                className={appStateContext?.state.isCosmosDBAvailable?.status !== CosmosDBStatus.NotConfigured ? styles.clearChatBroom : styles.clearChatBroomNoCosmos}
                                iconProps={{ iconName: 'Broom' }}
                                onClick={appStateContext?.state.isCosmosDBAvailable?.status !== CosmosDBStatus.NotConfigured ? clearChat : newChat}
                                disabled={disabledButton()}
                                aria-label="clear chat button"
                            />
                                <Dialog
                                    hidden={hideErrorDialog}
                                    onDismiss={handleErrorDialogClose}
                                    dialogContentProps={errorDialogContentProps}
                                    modalProps={modalProps}
                                >
                                </Dialog>
                            </Stack>
                            <QuestionInput
                                clearOnSend
                                placeholder="Type a new question..."
                                disabled={isLoading || isTypewriterActive} // DEV FIX: Check if Typewriter is active
                                onSend={(question, id) => {
                                     makeApiRequestWithCosmosDB(question, id)
                                }}
                                conversationId={appStateContext?.state.currentChat?.id ? appStateContext?.state.currentChat?.id : undefined}
                                defaultQuestion={defaultQuestion} 
                            />
                        </Stack>
                    </div>
                    {/* Citation Panel */}
                    {messages && messages.length > 0 && isCitationPanelOpen && activeCitation && (
                        <Stack.Item className={styles.citationPanel} tabIndex={0} role="tabpanel" aria-label="Citations Panel">
                            <Stack aria-label="Citations Panel Header Container" horizontal className={styles.citationPanelHeaderContainer} horizontalAlign="space-between" verticalAlign="center">
                                <span aria-label="Citations" className={styles.citationPanelHeader}>Citations</span>
                                <IconButton iconProps={{ iconName: 'Cancel' }} aria-label="Close citations panel" onClick={() => setIsCitationPanelOpen(false)} />
                            </Stack>
                            <h5 className={styles.citationPanelTitle} tabIndex={0} title={activeCitation.url && !activeCitation.url.includes("blob.core") ? activeCitation.url : activeCitation.title ?? ""} onClick={() => onViewSource(activeCitation)}>{activeCitation.title}</h5>
                            <div tabIndex={0}>
                            <ReactMarkdown
                                {...{
                                    linkTarget: "_blank",
                                    className: styles.citationPanelContent,
                                    remarkPlugins: [remarkGfm as Pluggable],
                                    rehypePlugins: [rehypeRaw]
                                } as any}
                                >
                                {DOMPurify.sanitize(activeCitation.chunk, {ALLOWED_TAGS: XSSAllowTags})}
                            </ReactMarkdown>
                            </div>
                        </Stack.Item>
                    )}
                    {(appStateContext?.state.isChatHistoryOpen && appStateContext?.state.isCosmosDBAvailable?.status !== CosmosDBStatus.NotConfigured) && <ChatHistoryPanel />}
                </Stack>
            )}
            {/* RIGHT MENU */}
            {!isMobile && (
                    
                    
                    <div className={`${styles.rightMenu} ${isRightMenuCollapsed ? styles.collapsed : ''}`}>

                        <div className={styles.collapseToggleWrapper}
                             style={{
                                right: isRightMenuCollapsed ? '20px' : '220px', 
                                transition: 'right 0.3s ease',
                                
                            }}
                            >
                            <img
                                src={collapse_icon}
                                alt={isRightMenuCollapsed ? "Expand Menu" : "Collapse Menu"}
                                // className={styles.collapseIcon}
                                 className={`${styles.collapseIcon} ${isRightMenuCollapsed ? styles.collapsedIcon : styles.expandedIcon}`}
                                onClick={() => setIsRightMenuCollapsed(!isRightMenuCollapsed)}
                            />
                            </div>
                    
                     {!isRightMenuCollapsed && (
                        <>
                    <div className={styles.section}>
                        <ProfileMenu/>                        
                        {/* <h3>Mentors</h3>
                        <ul>
                            <li><button disabled>Mentor TBD</button></li>
                            <li><button disabled>Mentor TBD</button></li>
                            <li><button disabled>Mentor TBD</button></li>
                            <li><button disabled>Mentor TBD</button></li>
                        </ul> */}
                    </div>

                    <div className={styles.section}>
                        <h3>REI Tools & Data</h3>
                        <ul>
                            <li><button onClick={() => window.open("https://trial.propstreampro.com/hbhs/", "_blank")} >Propstream</button></li>
                            {/* <li><button onClick={() => window.open("https://ari.aispeakly.com/", "_blank")} >AI Sales Training</button></li> */}
                            <li><button onClick={() => window.open("https://ari.uprankpro.com/", "_blank")} >AI Marketing</button></li>
                            {/* <li><button onClick={() => window.open("https://chatarv.ai?fpr=reilabs", "_blank")} >ChatARV</button></li>
                            <li><button onClick={() => window.open("https://leads.reilabs.ai/", "_blank")} >Tax-Lien Leads</button></li>
                            <li><button onClick={() => window.open("https://app.closebot.com/a?fpr=reilabs", "_blank")} >CloseBot</button></li> */}
                            {/* <li><button disabled>Brokerless</button></li> */}
                        </ul>
                    </div>

                    {/* <div className={styles.section}>
                        <h3>Professional Services</h3>
                        <ul>
                        <li><button disabled onClick={() =>
                                        handleSetPrompt(
                                        "Can I have a list of real estate attorneys in <CITY, STATE>"
                                        )
                                    }>Attorneys</button></li>
                            <li><button disabled>Title Companies</button></li>
                            <li><button disabled>HM Lenders</button></li>
                            <li><button disabled>PM Lenders</button></li>
                            <li><button disabled>Note Buyers</button></li>
                        </ul>
                    </div> */}

                    <div className={styles.section}>
                        <h3>REI Events</h3>
                        <ul>
                            {/* <a href='https://wholesalinglive.com/'><li><button>WSL 2025</button></li> </a> */}
                            {/* Add more if needed */}
                            <li>
                                <button onClick={() => window.open("https://wholesalinglive.com/", "_blank")}>
                                    WSL 2025
                                </button>
                                </li>
                        </ul>
                    </div>
                    </>
                     )}
                </div>
            )}
        </div>
    );
};

export default Chat;