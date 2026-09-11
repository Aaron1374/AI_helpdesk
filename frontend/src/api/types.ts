export type UserRole = 'employee' | 'l1' | 'l2' | 'support_lead' | 'admin';

export interface AuthUser {
  email: string;
  role: UserRole;
}

export interface LoginResponse {
  access_token: string;
  token_type: 'bearer';
  user: AuthUser;
}

export interface ApiErrorShape {
  detail?: string;
}

export interface ConversationResponse {
  id: string;
  status: string;
}

export interface ConversationItem {
  id: string;
  title: string;
  preview: string;
  owner_type: 'AI' | 'HUMAN';
  status: string;
  ticket_status: string | null;
  created_at: string | null;
  updated_at: string | null;
  message_count: number;
}

export interface AgentMessage {
  sender: string;
  content: string;
}

export interface MessageResponse {
  messages: AgentMessage[];
  status?: string;
  state?: WorkflowState;
}

export interface WorkflowState {
  category?: string;
  status?: string;
  escalate?: boolean;
  evidence?: unknown[];
  tool_history?: string[];
  retrieval_score?: number;
  sanitized_query?: string;
}

export interface TicketItem {
  id: string;
  title: string;
  status: string;
  conversation_id: string | null;
}

export interface SimilarIncident {
  type?: string;
  title: string;
  content: string;
  status?: string;
  similarity?: number;
}

export interface ChatMessageRecord {
  id: string;
  sender_type: 'USER' | 'AI' | 'SYSTEM';
  content: string;
  created_at: string | null;
}