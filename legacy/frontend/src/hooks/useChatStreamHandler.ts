// useChatStreamHandler.ts
import { useCallback, useRef, useContext, useState, useEffect } from 'react';
import { ChatMessage } from '../api/models';
import { AppStateContext } from '../state/AppProvider'; // or wherever your context is

export const useChatStreamHandler = () => {
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const contentAccumulators = useRef<Map<string, string>>(new Map()); // PER-MESSAGE ACCUMULATORS
    const isStoppingRef = useRef(false);

    // Pull in your appStateContext
    const appStateContext = useContext(AppStateContext);

    // ADD THIS LOGGING FOR MESSAGES ARRAY CHANGES
    // useEffect(() => {
    //     // console.log('🔥 STREAM HANDLER: Messages array updated, count:', messages.length);
    //     messages.forEach((msg, index) => {
    //         console.log(`📝 STREAM Message ${index}:`, {
    //             id: msg.id,
    //             role: msg.role,
    //             contentLength: msg.content?.length || 0,
    //             contentPreview: msg.content?.slice(0, 50) + '...'
    //         });
    //     });
    // }, [messages]);

    const processResultMessage = useCallback((
        resultMessage: ChatMessage,
        userMessage: ChatMessage,
        conversationId?: string
    ) => {
        const messageKey = userMessage.id; // Use message ID as key
        
        // console.log('🌊 STREAM: Processing result message:', {
        //     role: resultMessage.role,
        //     contentLength: resultMessage.content?.length,
        //     messageId: userMessage.id,
        //     conversationId,
        //     currentAccumulator: contentAccumulators.current.get(messageKey)?.length || 0,
        //     chunkContent: resultMessage.content // LOG THE ACTUAL CHUNK
        // });

        if (isStoppingRef.current) {
            // console.log('🛑 STREAM: Skipping message (stopping)');
            return; // Don't process messages if stopping
        }

        setMessages((prevMessages) => {
            // console.log('📊 STREAM: Before update - messages count:', prevMessages.length);
            // console.log('📊 STREAM: Before update - message IDs:', prevMessages.map(m => `${m.id}(${m.role})`));
            
            let newMessages = [...prevMessages];

            // 1. Ensure user message is in local state (for new convos)
            if (!conversationId && !newMessages.some(msg => msg.id === userMessage.id)) {
                // console.log('📝 STREAM: Adding user message to local state');
                newMessages = [...newMessages, userMessage];
            }

            // 2. Handle the assistant chunk
            if (resultMessage.role === 'assistant') {
                // Get or initialize accumulator for this specific message
                const currentContent = contentAccumulators.current.get(messageKey) || '';
                const newContent = currentContent + resultMessage.content;
                contentAccumulators.current.set(messageKey, newContent);
                
                // console.log('🤖 STREAM: Accumulator for message', messageKey, 'now has length:', newContent.length);
                // console.log('🤖 STREAM: Added chunk length:', resultMessage.content?.length);
                // console.log('🤖 STREAM: New content preview:', newContent.slice(-100)); // Show the end

                // Try to find existing assistant msg by ID
                const streamingIndex = newMessages.findIndex(
                    msg => msg.role === 'assistant' && msg.id === userMessage.id
                );

                // console.log('🔍 STREAM: Looking for assistant message with ID:', userMessage.id, 'Found at index:', streamingIndex);

                if (streamingIndex !== -1) {
                    // console.log('✏️ STREAM: Updating existing assistant message');
                    newMessages[streamingIndex] = {
                        ...newMessages[streamingIndex],
                        content: newContent
                    };
                } else {
                    // console.log('➕ STREAM: Creating new assistant message');
                    const updatedAssistantMessage = {
                        ...resultMessage,
                        content: newContent,
                        id: userMessage.id
                    };
                    newMessages.push(updatedAssistantMessage);
                }
            } 
            // 3. Or if it's a "tool" message
            else if (resultMessage.role === 'tool') {
                const existingToolIndex = newMessages.findIndex(
                    msg => msg.role === 'tool' && msg.id === `${userMessage.id}-tool`
                );

                if (existingToolIndex === -1) {
                    // console.log('🔧 STREAM: Adding tool message');
                    const toolMessage = {
                        ...resultMessage,
                        id: `${userMessage.id}-tool`
                    };
                    newMessages.push(toolMessage);
                }
            }

            // 4. Update context conversation if conversationId is known
            if (conversationId && appStateContext?.state?.currentChat?.id === conversationId) {
                // console.log('💾 STREAM: Updating context conversation');
                const updatedConversation = {
                    ...appStateContext.state.currentChat,
                    messages: newMessages,
                };
                // Dispatch that into context
                appStateContext.dispatch({ 
                    type: 'UPDATE_CURRENT_CHAT', 
                    payload: updatedConversation 
                });
            }

            // console.log('📊 STREAM: After update - messages count:', newMessages.length);
            // console.log('📊 STREAM: After update - message IDs:', newMessages.map(m => `${m.id}(${m.role})`));
            
            return newMessages;
        });
    }, [appStateContext]);

    // The rest is the same
    const resetStreamBuffer = useCallback((messageId?: string) => {
        // console.log('🔄 STREAM: Resetting stream buffer for message:', messageId || 'ALL');
        if (messageId) {
            // Reset specific message accumulator
            contentAccumulators.current.delete(messageId);
        } else {
            // Reset all accumulators
            contentAccumulators.current.clear();
        }
        isStoppingRef.current = false;
    }, []);

    const stopStreaming = useCallback(() => {
        // console.log('🛑 STREAM: Stopping streaming');
        isStoppingRef.current = true;
    }, []);

    return {
        messages,
        setMessages,
        processResultMessage,
        resetStreamBuffer,
        stopStreaming
    };
};