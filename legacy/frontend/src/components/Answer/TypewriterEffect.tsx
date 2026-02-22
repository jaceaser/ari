import React, { useState, useEffect, useRef, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Components } from 'react-markdown/lib/ast-to-react';
import styles from './TypewriterEffect.module.css';
import 'katex/dist/katex.min.css';

interface TypewriterEffectProps {
  text: string;
  speed?: number;
  chunkSize?: number;
  onComplete?: () => void;
  onStreamingComplete?: () => void;
  shouldStop?: boolean;  
  scrollToBottom?: () => void;
}

const TypewriterEffect: React.FC<TypewriterEffectProps> = ({ 
  text, 
  speed = 50,
  onComplete = () => {}, 
  onStreamingComplete = () => {},
  chunkSize = 3,
  shouldStop = false,
  scrollToBottom = () => {}
}) => {
  const [displayedText, setDisplayedText] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  
  // Use refs to track state without causing re-renders
  const fullTextRef = useRef('');
  const typingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isTypingRef = useRef(false);
  const streamingCompleteCalledRef = useRef(false);
  const currentIndexRef = useRef(0);
  const containerRef = useRef<HTMLDivElement>(null);

  const processSuperscript = (children: React.ReactNode): React.ReactNode => {
    if (typeof children === 'string') {
      const parts = children.split(/(\^[^\^]+\^)/g);
      return parts.map((part, index) => {
        if (part.startsWith('^') && part.endsWith('^')) {
          const content = part.slice(1, -1);
          return <sup key={index}>{content}</sup>;
        }
        return part;
      });
    }
    if (Array.isArray(children)) {
      return children.map((child, index) => processSuperscript(child));
    }
    if (React.isValidElement(children)) {
      return React.cloneElement(children, {
        ...children.props,
        children: processSuperscript(children.props.children)
      });
    }
    return children;
  };

  const components: Components = {
    code: ({ node, inline, className, children, ...props }) => (
      <code {...props}>
        {children}
      </code>
    ),
    a: ({ node, children, href, ...props }) => (
      <a 
        target="_blank"
        rel="noopener noreferrer"
        href={href}
        {...props}
      >
        {processSuperscript(children)}
      </a>
    ),
    blockquote: ({ node, children, ...props }) => (
      <blockquote {...props}>
        {processSuperscript(children)}
      </blockquote>
    ),
    p: ({ children }) => (
      <p>
        {processSuperscript(children)}
      </p>
    ),
    h1: ({ children }) => (
      <h1>
        {processSuperscript(children)}
      </h1>
    ),
    h2: ({ children }) => (
      <h2>
        {processSuperscript(children)}
      </h2>
    ),
    h3: ({ children }) => (
      <h3>
        {processSuperscript(children)}
      </h3>
    ),
    ul: ({ children }) => (
      <ul>
        {children}
      </ul>
    ),
    ol: ({ children }) => (
      <ol>
        {children}
      </ol>
    ),
    li: ({ children }) => (
      <li>
        {processSuperscript(children)}
      </li>
    )
  };

  // Cleanup function
  const cleanup = useCallback(() => {
    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current);
      typingTimeoutRef.current = null;
    }
  }, []);

  // Call onStreamingComplete only once when truly complete
  const callStreamingComplete = useCallback(() => {
    if (!streamingCompleteCalledRef.current) {
      streamingCompleteCalledRef.current = true;
      // console.log('TypewriterEffect: Calling onStreamingComplete');
      onStreamingComplete();
      scrollToBottom();
    }
  }, [onStreamingComplete, scrollToBottom]);

  // Main typing function
  const startTyping = useCallback(() => {
    if (isTypingRef.current) {
      return; // Already typing
    }

    isTypingRef.current = true;
    setIsTyping(true);
    
    const typeNextChunk = () => {
      const currentIndex = currentIndexRef.current;
      const targetText = fullTextRef.current;
      
      if (currentIndex >= targetText.length) {
        // Typing complete
        // console.log('TypewriterEffect: Typing complete');
        isTypingRef.current = false;
        setIsTyping(false);
        onComplete();
        callStreamingComplete();
        return;
      }

      // Calculate next chunk
      const nextIndex = Math.min(currentIndex + chunkSize, targetText.length);
      let chunk = targetText.slice(currentIndex, nextIndex);
      
      // Handle markdown symbols as complete units
      const markdownSymbols = ['**', '##', '```', '*', '_', '[', ']', '(', ')'];
      for (const symbol of markdownSymbols) {
        const symbolStart = targetText.indexOf(symbol, currentIndex);
        if (symbolStart !== -1 && symbolStart < nextIndex) {
          chunk = targetText.slice(currentIndex, symbolStart + symbol.length);
          break;
        }
      }
      
      // Update displayed text
      const newIndex = currentIndex + chunk.length;
      currentIndexRef.current = newIndex;
      setDisplayedText(targetText.slice(0, newIndex));
      
      // Continue typing if not at end
      if (newIndex < targetText.length && !shouldStop) {
        typingTimeoutRef.current = setTimeout(typeNextChunk, speed);
      } else {
        // Finished typing
        // console.log('TypewriterEffect: Typing finished');
        isTypingRef.current = false;
        setIsTyping(false);
        onComplete();
        callStreamingComplete();
      }
    };

    typeNextChunk();
  }, [speed, chunkSize, onComplete, callStreamingComplete, shouldStop]);

  // Handle new text arriving
  useEffect(() => {
    if (text !== fullTextRef.current) {
      // console.log(`TypewriterEffect: Text updated. Old length: ${fullTextRef.current.length}, New length: ${text.length}`);
      
      // If text completely changes (not just grows), reset everything
      if (text.length < fullTextRef.current.length || 
          (text.length > 0 && !text.startsWith(fullTextRef.current.slice(0, Math.min(50, text.length))))) {
        // console.log('TypewriterEffect: Text completely changed, resetting...');
        cleanup();
        currentIndexRef.current = 0;
        isTypingRef.current = false;
        setIsTyping(false);
        setDisplayedText('');
        streamingCompleteCalledRef.current = false;
      }
      
      // Reset streaming complete flag when new text arrives
      if (text.length > fullTextRef.current.length) {
        streamingCompleteCalledRef.current = false;
      }
      
      fullTextRef.current = text;
      
      // If we're not currently typing and there's new text to show, start typing
      if (!isTypingRef.current && currentIndexRef.current < text.length) {
        startTyping();
      }
    }
  }, [text, startTyping, cleanup]);

  // Handle shouldStop
  useEffect(() => {
    if (shouldStop && isTypingRef.current) {
      // console.log('TypewriterEffect: Stop requested, showing full text immediately');
      cleanup();
      
      // Show all text immediately
      setDisplayedText(fullTextRef.current);
      currentIndexRef.current = fullTextRef.current.length;
      isTypingRef.current = false;
      setIsTyping(false);
      
      // Call callbacks after a brief delay to ensure UI updates
      setTimeout(() => {
        onComplete();
        callStreamingComplete();
      }, 50);
    }
  }, [shouldStop, cleanup, onComplete, callStreamingComplete]);

  // Scroll effect
  useEffect(() => {
    if (containerRef.current) {
      window.requestAnimationFrame(() => {
        scrollToBottom();
      });
    }
  }, [displayedText, scrollToBottom]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      cleanup();
    };
  }, [cleanup]);

  if (!text) {
    return null;
  }

  return (
    <div className={styles.typewriterContainer}>
      <div className={styles.markdownContent} ref={containerRef}>
        <ReactMarkdown 
          remarkPlugins={[remarkGfm]}
          components={components}
        >
          {displayedText}
        </ReactMarkdown>
      </div>
    </div>
  );
};

export default TypewriterEffect;