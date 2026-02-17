/**
 * Plain TypeScript types for the ARI data model.
 * These match the shapes returned by the external API backend (Cosmos DB).
 * SQLite/Drizzle definitions have been removed — all persistence goes through the API.
 */

export interface User {
  id: string;
  email: string;
  password?: string | null;
  type?: "guest" | "regular";
}

export interface Chat {
  id: string;
  createdAt: number;
  title: string;
  userId: string;
  visibility: string;
  status?: string;
}

export interface DBMessage {
  id: string;
  chatId: string;
  role: string;
  parts: string;
  attachments: string;
  createdAt: number;
}

export interface Vote {
  chatId: string;
  messageId: string;
  isUpvoted: number;
}

export interface Document {
  id: string;
  createdAt: number;
  title: string;
  content: string | null;
  kind: string;
  userId: string;
}

export interface Suggestion {
  id: string;
  documentId: string;
  documentCreatedAt: number;
  originalText: string;
  suggestedText: string;
  description?: string | null;
  isResolved: number;
  userId: string;
  createdAt: number;
}

export interface Stream {
  id: string;
  chatId: string;
  createdAt: number;
}
