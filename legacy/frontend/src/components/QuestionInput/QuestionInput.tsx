import { useState, useEffect } from "react";
import { Stack, TextField } from "@fluentui/react";
import { SendRegular } from "@fluentui/react-icons";
import styles from "./QuestionInput.module.css";

interface Props {
    onSend: (question: string, id?: string) => void;
    disabled: boolean;
    placeholder?: string;
    clearOnSend?: boolean;
    conversationId?: string;
    defaultQuestion?: string;
}

export const QuestionInput = ({ 
    onSend, 
    disabled, 
    placeholder, 
    clearOnSend, 
    conversationId, 
    defaultQuestion 
}: Props) => {
    const [question, setQuestion] = useState<string>("");
    
    useEffect(() => {
        if (defaultQuestion !== undefined) {
            setQuestion(defaultQuestion);
        }
    }, [defaultQuestion]);

    const sendQuestion = () => {
        if (disabled || !question.trim()) {
            return;
        }

        if(conversationId){
            onSend(question, conversationId);
        }else{
            onSend(question);
        }

        if (clearOnSend) {
            setQuestion("");
        }
    };

    const onEnterPress = (ev: React.KeyboardEvent<Element>) => {
        if (ev.key === "Enter" && !ev.shiftKey && !(ev.nativeEvent?.isComposing === true)) {
            ev.preventDefault();
            sendQuestion();
        }
    };

    const onQuestionChange = (_ev: React.FormEvent<HTMLInputElement | HTMLTextAreaElement>, newValue?: string) => {
        setQuestion(newValue || "");
    };

    const sendQuestionDisabled = disabled || !question.trim();

    return (
        <Stack horizontal className={styles.questionInputContainer}>
            <TextField
                className={styles.questionInputTextArea}
                placeholder={placeholder}
                multiline
                resizable={false}
                borderless
                value={question}
                onChange={onQuestionChange}
                onKeyDown={onEnterPress}
                styles={{ // ← Fluent UI component-specific override
                    field: {
                      background: "#2d2d2d !important", // Temporary test
                      color: "#e0e0e0 !important",
                    }
                  }}
            />
            <div className={styles.questionInputSendButtonContainer} 
                role="button" 
                tabIndex={0}
                aria-label="Ask question button"
                onClick={sendQuestion}
                onKeyDown={e => e.key === "Enter" || e.key === " " ? sendQuestion() : null}
            >
                { sendQuestionDisabled ? 
                    <SendRegular className={styles.questionInputSendButtonDisabled}/>
                    :
                    // Update the img to use Fluent UI Icon with proper styling
                    <SendRegular className={styles.questionInputSendButton} />
                }
            </div>
            <div className={styles.questionInputBottomBorder} />
        </Stack>
    );
};
