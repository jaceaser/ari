import { FormEvent, useEffect, useMemo, useState, useContext, useCallback} from "react";
import { useBoolean } from "@fluentui/react-hooks"
import { Checkbox, Stack } from "@fluentui/react";
import { AppStateContext } from '../../state/AppProvider';
import ucAiLogo from "../../assets/uc-ai-logo.png";
import TypewriterEffect from "./TypewriterEffect";

import styles from "./Answer.module.css";

import { AskResponse, Citation, Feedback, historyMessageFeedback } from "../../api";
import { parseAnswer } from "./AnswerParser";
import { ThumbDislike20Filled, ThumbLike20Filled } from "@fluentui/react-icons";
import 'katex/dist/katex.min.css'; 

interface Props {
    answer: AskResponse;
    onCitationClicked: (citedDocument: Citation) => void;
    onStreamingComplete?: () => void;
    shouldStop?: boolean;
    scrollToBottom?: () => void;
    requestId?: string; // Add this to track different requests
}

export const Answer = ({
    answer,
    onCitationClicked,
    onStreamingComplete,
    shouldStop,
    scrollToBottom,
    requestId
}: Props) => {
    const initializeAnswerFeedback = (answer: AskResponse) => {
        if (answer.message_id == undefined) return undefined;
        if (answer.feedback == undefined) return undefined;
        if (answer.feedback.split(",").length > 1) return Feedback.Negative;
        if (Object.values(Feedback).includes(answer.feedback)) return answer.feedback;
        return Feedback.Neutral;
    }

    const [isRefAccordionOpen, { toggle: toggleIsRefAccordionOpen }] = useBoolean(false);
    const filePathTruncationLimit = 50;

    const parsedAnswer = useMemo(() => {
        // console.log('Answer: Parsing answer with length:', answer.answer?.length || 0);
        const result = parseAnswer(answer);
        // console.log('Answer: Parsed result text length:', result.markdownFormatText?.length || 0);
        return result;
    }, [answer]);
    const [chevronIsExpanded, setChevronIsExpanded] = useState(isRefAccordionOpen);
    const [feedbackState, setFeedbackState] = useState(initializeAnswerFeedback(answer));
    const [isFeedbackDialogOpen, setIsFeedbackDialogOpen] = useState(false);
    const [showReportInappropriateFeedback, setShowReportInappropriateFeedback] = useState(false);
    const [negativeFeedbackList, setNegativeFeedbackList] = useState<Feedback[]>([]);
    const appStateContext = useContext(AppStateContext)
    const FEEDBACK_ENABLED = appStateContext?.state.frontendSettings?.feedback_enabled && appStateContext?.state.isCosmosDBAvailable?.cosmosDB; 

    // REMOVED: visibleText, chatEventHandler, onMessageHandler - these were unused

    const handleChevronClick = () => {
        setChevronIsExpanded(!chevronIsExpanded);
        toggleIsRefAccordionOpen();
    };

    // // ADD THIS INSIDE THE Answer COMPONENT, RIGHT AFTER THE PROPS DESTRUCTURING:
    // useEffect(() => {
    //     console.log('✅ ANSWER: Component mounted for message:', answer.message_id);
    //     return () => {
    //         console.log('❌ ANSWER: Component unmounting for message:', answer.message_id);
    //     };
    // }, [answer.message_id]);

    // ALSO ADD THIS TO DETECT WHEN ANSWER CONTENT DISAPPEARS:
    // useEffect(() => {
    //     if (!answer || !answer.answer) {
    //         console.warn('⚠️ ANSWER: Answer disappeared! Answer object:', answer);
    //     } else {
    //         console.log('📄 ANSWER: Answer content length:', answer.answer?.length);
    //     }
    // }, [answer]);

    useEffect(() => {
        setChevronIsExpanded(isRefAccordionOpen);
    }, [isRefAccordionOpen]);

    useEffect(() => {
        if (answer.message_id == undefined) return;
        
        let currentFeedbackState;
        if (appStateContext?.state.feedbackState && appStateContext?.state.feedbackState[answer.message_id]) {
            currentFeedbackState = appStateContext?.state.feedbackState[answer.message_id];
        } else {
            currentFeedbackState = initializeAnswerFeedback(answer);
        }
        setFeedbackState(currentFeedbackState)
    }, [appStateContext?.state.feedbackState, feedbackState, answer.message_id]);

    // create an In-memory object to cache API responses 
    const responseCache = useMemo(() => new Map<string, any>(), []);

    // create a debounce() function to ensure to optimize the no. of requests sent via the API call in the backend
    const debounce = (func: Function, delay: number) => {
        let timeoutId: number; 
        return (...args: any[]) => {
            clearTimeout(timeoutId);
            timeoutId = window.setTimeout(() => func(...args), delay);
        };
    };

    const debouncedHistoryMessageFeedback = useCallback(debounce(async (messageId: string, feedback: Feedback) => {
        // Check if response is cached 
        if (responseCache.has(`${messageId}-${feedback}`)) {
            // console.log("Using cached response");
            return;
        }
        // Call API and cache the response 
        const response = await historyMessageFeedback(messageId, feedback);
        responseCache.set(`${messageId}-${feedback}`, response);
    }, 500), [responseCache]);

    const createCitationFilepath = (citation: Citation, index: number, truncate: boolean = false) => {
        let citationFilename = "";

        if (citation.filename) {
            const part_i = citation.part_index ?? (citation.chunk_id ? parseInt(citation.chunk_id) + 1 : '');
            if (truncate && citation.filename.length > filePathTruncationLimit) {
                const citationLength = citation.filename.length;
                citationFilename = `${citation.filename.substring(0, 20)}...${citation.filename.substring(citationLength - 20)} - Part ${part_i}`;
            }
            else {
                citationFilename = `${citation.filename} - Part ${part_i}`;
            }
        }
        else if (citation.filename && citation.reindex_id) {
            citationFilename = `${citation.filename} - Part ${citation.reindex_id}`;
        }
        else {
            citationFilename = `Citation ${index}`;
        }
        return citationFilename;
    }

    const onLikeResponseClicked = async () => {
        if (answer.message_id == undefined) return;

        let newFeedbackState = feedbackState;
        // Set or unset the thumbs up state
        if (feedbackState == Feedback.Positive) {
            newFeedbackState = Feedback.Neutral;
        }
        else {
            newFeedbackState = Feedback.Positive;
        }
        appStateContext?.dispatch({ type: 'SET_FEEDBACK_STATE', payload: { answerId: answer.message_id, feedback: newFeedbackState } });
        setFeedbackState(newFeedbackState);

        // Update message feedback using our custom cached debouncing
        debouncedHistoryMessageFeedback(answer.message_id, newFeedbackState);
    }

    const onDislikeResponseClicked = async () => {
        if (answer.message_id == undefined) return;

        let newFeedbackState = feedbackState;
        if (feedbackState === undefined || feedbackState === Feedback.Neutral || feedbackState === Feedback.Positive) {
            newFeedbackState = Feedback.Negative;
            setFeedbackState(newFeedbackState);
            setIsFeedbackDialogOpen(true);
        } else {
            // Reset negative feedback to neutral
            newFeedbackState = Feedback.Neutral;
            setFeedbackState(newFeedbackState);

            // Update message feedback using our custom cached debouncing
            debouncedHistoryMessageFeedback(answer.message_id, Feedback.Neutral);
        }
        appStateContext?.dispatch({ type: 'SET_FEEDBACK_STATE', payload: { answerId: answer.message_id, feedback: newFeedbackState }});
    }

    const updateFeedbackList = (ev?: FormEvent<HTMLElement | HTMLInputElement>, checked?: boolean) => {
        if (answer.message_id == undefined) return;
        let selectedFeedback = (ev?.target as HTMLInputElement)?.id as Feedback;

        let feedbackList = negativeFeedbackList.slice();
        if (checked) {
            feedbackList.push(selectedFeedback);
        } else {
            feedbackList = feedbackList.filter((f) => f !== selectedFeedback);
        }

        setNegativeFeedbackList(feedbackList);
    };

    const onSubmitNegativeFeedback = async () => {
        if (answer.message_id == undefined) return;
        await historyMessageFeedback(answer.message_id, negativeFeedbackList.join(","));
        resetFeedbackDialog();
    }

    const resetFeedbackDialog = () => {
        setIsFeedbackDialogOpen(false);
        setShowReportInappropriateFeedback(false);
        setNegativeFeedbackList([]);
    }

    const UnhelpfulFeedbackContent = () => {
        return (<>
            <div>Why wasn't this response helpful?</div>
            <Stack tokens={{childrenGap: 4}}>
                <Checkbox label="Citations are missing" id={Feedback.MissingCitation} defaultChecked={negativeFeedbackList.includes(Feedback.MissingCitation)} onChange={updateFeedbackList}></Checkbox>
                <Checkbox label="Citations are wrong" id={Feedback.WrongCitation} defaultChecked={negativeFeedbackList.includes(Feedback.WrongCitation)} onChange={updateFeedbackList}></Checkbox>
                <Checkbox label="The response is not from my data" id={Feedback.OutOfScope} defaultChecked={negativeFeedbackList.includes(Feedback.OutOfScope)} onChange={updateFeedbackList}></Checkbox>
                <Checkbox label="Inaccurate or irrelevant" id={Feedback.InaccurateOrIrrelevant} defaultChecked={negativeFeedbackList.includes(Feedback.InaccurateOrIrrelevant)} onChange={updateFeedbackList}></Checkbox>
                <Checkbox label="Other" id={Feedback.OtherUnhelpful} defaultChecked={negativeFeedbackList.includes(Feedback.OtherUnhelpful)} onChange={updateFeedbackList}></Checkbox>
            </Stack>
            <div onClick={() => setShowReportInappropriateFeedback(true)} style={{ color: "#115EA3", cursor: "pointer"}}>Report inappropriate content</div>
        </>);
    }

    const ReportInappropriateFeedbackContent = () => {
        return (
            <>
                <div>The content is <span style={{ color: "red" }} >*</span></div>
                <Stack tokens={{childrenGap: 4}}>
                    <Checkbox label="Hate speech, stereotyping, demeaning" id={Feedback.HateSpeech} defaultChecked={negativeFeedbackList.includes(Feedback.HateSpeech)} onChange={updateFeedbackList}></Checkbox>
                    <Checkbox label="Violent: glorification of violence, self-harm" id={Feedback.Violent} defaultChecked={negativeFeedbackList.includes(Feedback.Violent)} onChange={updateFeedbackList}></Checkbox>
                    <Checkbox label="Sexual: explicit content, grooming" id={Feedback.Sexual} defaultChecked={negativeFeedbackList.includes(Feedback.Sexual)} onChange={updateFeedbackList}></Checkbox>
                    <Checkbox label="Manipulative: devious, emotional, pushy, bullying" defaultChecked={negativeFeedbackList.includes(Feedback.Manipulative)} id={Feedback.Manipulative} onChange={updateFeedbackList}></Checkbox>
                    <Checkbox label="Other" id={Feedback.OtherHarmful} defaultChecked={negativeFeedbackList.includes(Feedback.OtherHarmful)} onChange={updateFeedbackList}></Checkbox>
                </Stack>
            </>
        );
    }

    const handleStreamingComplete = useCallback(() => {
        // console.log('Answer: Streaming complete callback received');
        // console.log('Answer: Final displayed text length:', parsedAnswer.markdownFormatText?.length || 0);
        onStreamingComplete?.();
    }, [onStreamingComplete, parsedAnswer.markdownFormatText]);

    return (
        <>
            <Stack className={styles.answerContainer} tabIndex={0}>
                <Stack horizontal verticalAlign="start" tokens={{ childrenGap: 8 }}>
                    {/* Image as the top-left icon */}
                    <img src={ucAiLogo} alt="ARI Logo" className={styles.topIcon} />
                    <Stack.Item grow>
                        <Stack horizontal grow>
                            <Stack.Item grow>
                                <TypewriterEffect
                                    key={requestId || answer.message_id} // Force re-mount on new requests
                                    text={parsedAnswer.markdownFormatText}
                                    speed={10}
                                    onStreamingComplete={handleStreamingComplete}
                                    shouldStop={shouldStop}
                                    scrollToBottom={scrollToBottom}
                                />
                            </Stack.Item>
                            <Stack.Item className={styles.answerHeader}>
                                {FEEDBACK_ENABLED && answer.message_id !== undefined && (
                                    <Stack horizontal horizontalAlign="space-between">
                                        <ThumbLike20Filled
                                            aria-hidden="false"
                                            aria-label="Like this response"
                                            onClick={() => onLikeResponseClicked()}
                                            style={
                                                feedbackState === Feedback.Positive ||
                                                appStateContext?.state.feedbackState[answer.message_id] ===
                                                    Feedback.Positive
                                                    ? { color: "darkgreen", cursor: "pointer" }
                                                    : { color: "slategray", cursor: "pointer" }
                                            }
                                        />
                                        <ThumbDislike20Filled
                                            aria-hidden="false"
                                            aria-label="Dislike this response"
                                            onClick={() => onDislikeResponseClicked()}
                                            style={
                                                feedbackState !== Feedback.Positive &&
                                                feedbackState !== Feedback.Neutral &&
                                                feedbackState !== undefined
                                                    ? { color: "darkred", cursor: "pointer" }
                                                    : { color: "slategray", cursor: "pointer" }
                                            }
                                        />
                                    </Stack>
                                )}
                            </Stack.Item>
                        </Stack>
                    </Stack.Item>
                </Stack>
                {chevronIsExpanded && (
                    <div
                        style={{
                            marginTop: 8,
                            display: "flex",
                            flexFlow: "wrap column",
                            maxHeight: "150px",
                            gap: "4px",
                        }}
                    >
                        {parsedAnswer.citations.map((citation, idx) => {
                            return (
                                <span
                                    title={createCitationFilepath(citation, ++idx)}
                                    tabIndex={0}
                                    role="link"
                                    key={idx}
                                    onClick={() => onCitationClicked(citation)}
                                    onKeyDown={(e) =>
                                        e.key === "Enter" || e.key === " "
                                            ? onCitationClicked(citation)
                                            : null
                                    }
                                    className={styles.citationContainer}
                                    aria-label={createCitationFilepath(citation, idx)}
                                >
                                    <div className={styles.citation}>{idx}</div>
                                    {createCitationFilepath(citation, idx, true)}
                                </span>
                            );
                        })}
                    </div>
                )}
            </Stack>
        </>
    );
};