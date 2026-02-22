import { UserInfo, ConversationRequest, Conversation, ChatMessage, CosmosDBHealth, CosmosDBStatus } from "./models";
import { chatHistorySampleData } from "../constants/chatHistory";

function getWebSocketURL(endpoint: string): string {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    return `${protocol}//${host}${endpoint}`;
}

// Example usage:

export async function conversationApi(
    options: ConversationRequest,
    onMessage: (message: string) => void,
    abortSignal: AbortSignal,
    endpoint: string = '/ws/conversation'
): Promise<void> {
    return new Promise<void>((resolve, reject) => {
        const wsURL = getWebSocketURL(endpoint);
        const client = new WebSocket(wsURL);

        let isAborted = false;
        let buffer = "";
        let bufferTimeout: ReturnType<typeof setTimeout> | null = null;
        let pingInterval: ReturnType<typeof setInterval> | null = null;
        let connectionTimeout: ReturnType<typeof setTimeout> | null = null;

        const processCitations = (text: string) => {
            let processed = text.replace(/\[doc\d+\](\s*\[doc\d+\])*/g, '');
            processed = processed.replace(/\s+([.,!?])/g, '$1');
            return processed;
        };

        const flushBuffer = () => {
            if (buffer && !isAborted) {
                const processedText = processCitations(buffer);
                onMessage(processedText);
                buffer = "";
            }
        };

        const cleanup = () => {
            if (pingInterval) {
                clearInterval(pingInterval);
                pingInterval = null;
            }
            if (bufferTimeout) {
                clearTimeout(bufferTimeout);
                bufferTimeout = null;
            }
            if (connectionTimeout) {
                clearTimeout(connectionTimeout);
                connectionTimeout = null;
            }
            abortSignal.removeEventListener("abort", abortListener);
        };

        const abortListener = () => {
            // console.log("WebSocket operation aborted by user");
            isAborted = true;
            cleanup();
            buffer = "";
            
            if (client.readyState === WebSocket.OPEN || client.readyState === WebSocket.CONNECTING) {
                client.close(1000, "Operation aborted by user");
            }
        };
        
        abortSignal.addEventListener("abort", abortListener);

        // Set up connection timeout (30 seconds)
        connectionTimeout = setTimeout(() => {
            if (client.readyState === WebSocket.CONNECTING) {
                console.error("WebSocket connection timeout");
                cleanup();
                client.close(1006, "Connection timeout");
                reject(new Error("Connection timeout"));
            }
        }, 30000);

        client.onopen = () => {
            // console.log("WebSocket connection opened.");
            
            // Clear connection timeout
            if (connectionTimeout) {
                clearTimeout(connectionTimeout);
                connectionTimeout = null;
            }
            
            // Send initial request
            client.send(JSON.stringify(options));
            
            // Set up keepalive ping every 4 minutes (240 seconds)
            // This is less than your 5-minute server timeout
            pingInterval = setInterval(() => {
                if (client.readyState === WebSocket.OPEN && !isAborted) {
                    // console.log("Sending keepalive ping");
                    client.send(JSON.stringify({ type: "ping" }));
                }
            }, 240000); // 4 minutes
        };

        client.onmessage = (event) => {
            if (isAborted) {
                return;
            }
        
            try {
                const data = JSON.parse(event.data);
                
                if (data.type === "pong") {
                    // console.log("Received pong from server - connection alive");
                    return;
                } 
                
                if (data.choices || data.messages) {
                    const messageContent = data.choices[0].messages[0].content;
                    if (messageContent) {
                        const processedContent = processCitations(messageContent);
                        const processedData = {
                            ...data,
                            choices: [{
                                ...data.choices[0],
                                messages: [{
                                    ...data.choices[0].messages[0],
                                    content: processedContent
                                }]
                            }]
                        };
                        onMessage(processedData);
                    }
                } else if (data.error) {
                    console.error("Error received from server:", data.error);
                    cleanup();
                    reject(new Error(data.error));
                    return;
                }
            } catch (error) {
                if (!isAborted) {
                    console.error("Error parsing WebSocket message:", error, event.data);
                    cleanup();
                    client.close(1002, "Invalid message format");
                    reject(error);
                }
            }
        };

        client.onerror = (error) => {
            if (!isAborted) {
                console.error("WebSocket error:", error);
                isAborted = true;
                cleanup();
                
                // Try to close cleanly if still connected
                if (client.readyState === WebSocket.OPEN) {
                    client.close(1011, "Client encountered error");
                }
                
                reject(new Error("WebSocket connection error"));
            }
        };

        client.onclose = (event) => {
            // console.log(`WebSocket connection closed. Code: ${event.code}, Reason: ${event.reason}`);
            cleanup();

            if (!isAborted) {
                // Handle different close codes
                switch (event.code) {
                    case 1000: // Normal closure
                        flushBuffer();
                        resolve();
                        break;
                    case 1001: // Going away (like timeout)
                        console.warn("Connection timed out on server");
                        reject(new Error("Connection timed out"));
                        break;
                    case 1006: // Abnormal closure
                        console.error("Connection closed abnormally");
                        reject(new Error("Connection lost unexpectedly"));
                        break;
                    case 1011: // Internal error
                        console.error("Server internal error");
                        reject(new Error("Server encountered an internal error"));
                        break;
                    default:
                        if (event.code >= 4000) {
                            // Custom error codes
                            reject(new Error(event.reason || `Custom error: ${event.code}`));
                        } else {
                            reject(new Error(event.reason || "WebSocket closed unexpectedly"));
                        }
                }
            } else {
                // Was aborted, so resolve normally
                flushBuffer();
                resolve();
            }
        };
    });
}


export async function getUserInfo(): Promise<UserInfo[]> {
    const response = await fetch('/.auth/me');
    if (!response.ok) {
        // console.log("No identity provider found. Access to chat will be blocked.")
        return [];
    }

    const payload = await response.json();
    return payload;
}

// export const fetchChatHistoryInit = async (): Promise<Conversation[] | null> => {
export const fetchChatHistoryInit = (): Conversation[] | null => {
    // Make initial API call here

    // return null;
    return chatHistorySampleData;
}

export const historyList = async (offset=0): Promise<Conversation[] | null> => {
    const response = await fetch(`/history/list?offset=${offset}`, {
        method: "GET",
    }).then(async (res) => {
        const payload = await res.json();
        if (!Array.isArray(payload)) {
            console.error("There was an issue fetching your data.");
            return null;
        }
        const conversations: Conversation[] = await Promise.all(payload.map(async (conv: any) => {
            let convMessages: ChatMessage[] = [];
            convMessages = await historyRead(conv.id)
            .then((res) => {
                return res
            })
            .catch((err) => {
                console.error("error fetching messages: ", err)
                return []
            })
            const conversation: Conversation = {
                id: conv.id,
                title: conv.title,
                date: conv.createdAt,
                messages: convMessages
            };
            return conversation;
        }));
        return conversations;
    }).catch((err) => {
        console.error("There was an issue fetching your data.");
        return null
    })

    return response
}

export const historyRead = async (convId: string): Promise<ChatMessage[]> => {
    const response = await fetch("/history/read", {
        method: "POST",
        body: JSON.stringify({
            conversation_id: convId
        }),
        headers: {
            "Content-Type": "application/json"
        },
    })
    .then(async (res) => {
        if(!res){
            return []
        }
        const payload = await res.json();
        let messages: ChatMessage[] = [];
        if(payload?.messages){
            payload.messages.forEach((msg: any) => {
                const message: ChatMessage = {
                    id: msg.id,
                    role: msg.role,
                    date: msg.createdAt,
                    content: msg.content,
                    feedback: msg.feedback ?? undefined
                }
                messages.push(message)
            });
        }
        return messages;
    }).catch((err) => {
        console.error("There was an issue fetching your data.");
        return []
    })
    return response
}

export const historyUpdate = async (messages: ChatMessage[], convId: string): Promise<Response> => {
    const response = await fetch("/history/update", {
        method: "POST",
        body: JSON.stringify({
            conversation_id: convId,
            messages: messages
        }),
        headers: {
            "Content-Type": "application/json"
        },
    }).then(async (res) => {
        return res
    })
    .catch((err) => {
        console.error("There was an issue fetching your data.");
        let errRes: Response = {
            ...new Response,
            ok: false,
            status: 500,
        }
        return errRes;
    })
    return response
}

export const historyDelete = async (convId: string) : Promise<Response> => {
    const response = await fetch("/history/delete", {
        method: "DELETE",
        body: JSON.stringify({
            conversation_id: convId,
        }),
        headers: {
            "Content-Type": "application/json"
        },
    })
    .then((res) => {
        return res
    })
    .catch((err) => {
        console.error("There was an issue fetching your data.");
        let errRes: Response = {
            ...new Response,
            ok: false,
            status: 500,
        }
        return errRes;
    })
    return response;
}

export const historyDeleteAll = async () : Promise<Response> => {
    const response = await fetch("/history/delete_all", {
        method: "DELETE",
        body: JSON.stringify({}),
        headers: {
            "Content-Type": "application/json"
        },
    })
    .then((res) => {
        return res
    })
    .catch((err) => {
        console.error("There was an issue fetching your data.");
        let errRes: Response = {
            ...new Response,
            ok: false,
            status: 500,
        }
        return errRes;
    })
    return response;
}

export const historyClear = async (convId: string) : Promise<Response> => {
    const response = await fetch("/history/clear", {
        method: "POST",
        body: JSON.stringify({
            conversation_id: convId,
        }),
        headers: {
            "Content-Type": "application/json"
        },
    })
    .then((res) => {
        return res
    })
    .catch((err) => {
        console.error("There was an issue fetching your data.");
        let errRes: Response = {
            ...new Response,
            ok: false,
            status: 500,
        }
        return errRes;
    })
    return response;
}

export const historyRename = async (convId: string, title: string) : Promise<Response> => {
    const response = await fetch("/history/rename", {
        method: "POST",
        body: JSON.stringify({
            conversation_id: convId,
            title: title
        }),
        headers: {
            "Content-Type": "application/json"
        },
    })
    .then((res) => {
        return res
    })
    .catch((err) => {
        console.error("There was an issue fetching your data.");
        let errRes: Response = {
            ...new Response,
            ok: false,
            status: 500,
        }
        return errRes;
    })
    return response;
}

export const historyEnsure = async (): Promise<CosmosDBHealth> => {
    const response = await fetch("/history/ensure", {
        method: "GET",
    })
    .then(async res => {
        let respJson = await res.json();
        let formattedResponse;
        if(respJson.message){
            formattedResponse = CosmosDBStatus.Working
        }else{
            if(res.status === 500){
                formattedResponse = CosmosDBStatus.NotWorking
            }else if(res.status === 401){
                formattedResponse = CosmosDBStatus.InvalidCredentials    
            }else if(res.status === 422){ 
                formattedResponse = respJson.error    
            }else{
                formattedResponse = CosmosDBStatus.NotConfigured
            }
        }
        if(!res.ok){
            return {
                cosmosDB: false,
                status: formattedResponse
            }
        }else{
            return {
                cosmosDB: true,
                status: formattedResponse
            }
        }
    })
    .catch((err) => {
        console.error("There was an issue fetching your data.");
        return {
            cosmosDB: false,
            status: err
        }
    })
    return response;
}

export const frontendSettings = async (): Promise<Response | null> => {
    const response = await fetch("/frontend_settings", {
        method: "GET",
    }).then((res) => {
        return res.json()
    }).catch((err) => {
        console.error("There was an issue fetching your data.");
        return null
    })

    return response
}
export const historyMessageFeedback = async (messageId: string, feedback: string): Promise<Response> => {
    const response = await fetch("/history/message_feedback", {
        method: "POST",
        body: JSON.stringify({
            message_id: messageId,
            message_feedback: feedback
        }),
        headers: {
            "Content-Type": "application/json"
        },
    })
    .then((res) => {
        return res
    })
    .catch((err) => {
        console.error("There was an issue logging feedback.");
        let errRes: Response = {
            ...new Response,
            ok: false,
            status: 500,
        }
        return errRes;
    })
    return response;
}