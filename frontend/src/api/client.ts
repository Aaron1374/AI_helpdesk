import type { ApiErrorShape, ConversationResponse, LoginResponse, MessageResponse, SignupResponse} from './types';
import { getToken } from '../auth/session';

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? '/api';

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function parseError(response: Response): Promise<ApiError> {
  let message = `Request failed (${response.status})`;
  try {
    const payload = (await response.json()) as ApiErrorShape;
    if (typeof payload?.detail === 'string') {
      message = payload.detail;
    } else if (Array.isArray(payload?.detail)) {
      message = payload.detail
        .map((item: any) => {
          if (typeof item === 'string') return item;
          const msg = item?.msg || JSON.stringify(item);
          const field = Array.isArray(item?.loc)
            ? item.loc.filter((part: any) => part !== 'body').join('.')
            : '';
          const cleanMsg = typeof msg === 'string' ? msg.replace(/^Value error,\s*/i, '') : msg;
          return field ? `${field}: ${cleanMsg}` : cleanMsg;
        })
        .join(', ');
    } else if (payload?.message && typeof payload.message === 'string') {
      message = payload.message;
    } else if (payload?.detail && typeof payload.detail === 'object') {
      message = JSON.stringify(payload.detail);
    }
  } catch {
    // Use the HTTP status when the server did not return JSON.
  }
  return new ApiError(message, response.status);
}


export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');

  const response = await fetch(`${apiBaseUrl}${path}`, { ...init, headers });
  if (!response.ok) throw await parseError(response);
  return (await response.json()) as T;
}

export function login(username: string, password: string): Promise<LoginResponse> {
  const body = new URLSearchParams({ username, password });
  return request<LoginResponse>('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body,
  });
}

export function signup(
  name: string,
  email: string,
  password: string,
  role: 'employee' | 'engineer' | 'admin',
  department: string,
): Promise<SignupResponse> {
  return request<SignupResponse>('/auth/signup', {
    method: 'POST',
    body: JSON.stringify({
      name,
      email,
      password,
      role,
      department,
    }),
  });
}

export function getMe(): Promise<{ user: import('./types').AuthUser }> {
  return request<{ user: import('./types').AuthUser }>('/auth/me');
}

export function createConversation(): Promise<ConversationResponse> {
  return request<ConversationResponse>('/conversations', { method: 'POST' });
}

export function getConversations(): Promise<import('./types').ConversationItem[]> {
  return request<import('./types').ConversationItem[]>('/conversations');
}

export function sendMessage(conversationId: string, content: string): Promise<MessageResponse> {
  return request<MessageResponse>(`/conversations/${conversationId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ content }),
  });
}

export function getTickets(): Promise<import('./types').TicketItem[]> {
  return request<import('./types').TicketItem[]>('/tickets');
}

export function getSimilarTickets(ticketId: string): Promise<import('./types').SimilarIncident[]> {
  return request<import('./types').SimilarIncident[]>(`/tickets/${ticketId}/similar`);
}

export function takeoverConversation(conversationId: string): Promise<{ status: string }> {
  return request<{ status: string }>(`/conversations/${conversationId}/takeover`, {
    method: 'POST',
  });
}

export function getConversationMessages(conversationId: string): Promise<import('./types').ChatMessageRecord[]> {
  return request<import('./types').ChatMessageRecord[]>(`/conversations/${conversationId}/messages`);
}

export function resolveTicket(ticketId: string): Promise<{ status: string; ticket_status: string }> {
  return request<{ status: string; ticket_status: string }>(`/tickets/${ticketId}/resolve`, {
    method: 'POST',
  });
}

export function closeConversation(conversationId: string): Promise<{ status: string; conversation_id: string }> {
  return request<{ status: string; conversation_id: string }>(`/conversations/${conversationId}/close`, {
    method: 'POST',
  });
}

export function confirmResolution(ticketId: string): Promise<{ status: string }> {
  return request<{ status: string }>(`/tickets/${ticketId}/confirm-resolution`, {
    method: 'POST',
  });
}