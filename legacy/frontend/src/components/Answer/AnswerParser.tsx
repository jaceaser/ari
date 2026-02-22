import { AskResponse, Citation } from "../../api";
import { cloneDeep } from "lodash-es";

import React from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeKatex from 'rehype-katex';
import remarkMath from 'remark-math';
import "katex/dist/katex.min.css";
import { Pluggable } from 'unified';


type ParsedAnswer = {
    citations: Citation[];
    markdownFormatText: string;
};

const enumerateCitations = (citations: Citation[]) => {
    const filepathMap = new Map();
    for (const citation of citations) {
        const { filename } = citation;
        let part_i = 1
        if (filepathMap.has(filename)) {
            part_i = filepathMap.get(filename) + 1;
        }
        filepathMap.set(filename, part_i);
        citation.part_index = part_i;
    }
    return citations;
}

export function parseAnswer(answer: AskResponse): ParsedAnswer {
    let answerText = answer.answer;
    const citationLinks = answerText.match(/\[(doc\d\d?\d?)]/g);

    const lengthDocN = "[doc".length;

    let filteredCitations = [] as Citation[];
    let citationReindex = 0;
    citationLinks?.forEach(link => {
        // Replacing the links/citations with number
        let citationIndex = link.slice(lengthDocN, link.length - 1);
        let citation = cloneDeep(answer.citations[Number(citationIndex) - 1]) as Citation;
        if (!filteredCitations.find((c) => c.id === citationIndex) && citation) {
          answerText = answerText.replaceAll(link, ` ^${++citationReindex}^ `);
          citation.id = citationIndex; // original doc index to de-dupe
          citation.reindex_id = citationReindex.toString(); // reindex from 1 for display
          filteredCitations.push(citation);
        }
    })

    filteredCitations = enumerateCitations(filteredCitations);

    return {
        citations: filteredCitations,
        markdownFormatText: answerText
    };
}

// A function to render the chat responses with latex formatting on the parsed answer using React markdown
export function RenderAnswer({ parsedAnswer }: { parsedAnswer: ParsedAnswer }) {
    return (
        <ReactMarkdown
            rehypePlugins={[rehypeKatex as any]}
            remarkPlugins={[remarkMath as any]}
        >
            {parsedAnswer.markdownFormatText}
        </ReactMarkdown>
    );
}