export interface FlightOffer {
  offer_id: string;
  airline_code: string;
  airline_name: string;
  flight_number: string;
  origin: string;
  destination: string;
  departure_time: string;
  arrival_time: string;
  duration_minutes: number;
  stops: number;
  cabin_class: string;
  total_price: number;
  currency: string;
  score?: number;
  rank?: number;
  match_reasons?: string[];
}

export interface HotelOffer {
  hotel_id: string;
  name: string;
  city: string;
  star_rating: number;
  price_per_night: number;
  currency: string;
  address?: string;
  amenities?: string[];
}

export interface RAGCitation {
  document: string;
  document_id?: string;
  page?: number;
  section?: string;
  relevance_score: number;
  snippet?: string;
}

export interface PendingAction {
  action_id: string;
  action_type: string;
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' | string;
  description: string;
  parameters: Record<string, any>;
  status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'EXECUTED' | string;
  created_at: string;
  operator_id?: string;
  operator_notes?: string;
}

export interface AgentMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp?: string;
}

export interface PolicyResponse {
  answer: string;
  sources: RAGCitation[];
  confidence_score?: number;
  retrieval_latency_ms?: number;
  total_latency_ms?: number;
}

export interface AgentChatResponse {
  thread_id: string;
  workflow: 'SEARCH' | 'POLICY' | 'DISRUPTION_REBOOKING' | 'HOTEL' | 'UNKNOWN' | string;
  response_message: string;
  messages: AgentMessage[];
  flight_results: FlightOffer[];
  hotel_results: HotelOffer[];
  policy_response?: PolicyResponse | null;
  disruption_plan?: Record<string, any> | null;
  pending_action?: PendingAction | null;
  requires_human_confirmation: boolean;
  confirmation_status: string;
  trace: string[];
}

export interface CacheStats {
  backend: string;
  hits: number;
  misses: number;
  writes: number;
  deletes: number;
  hit_rate: number;
  keys_count: number;
}

export interface ServiceStatus {
  status: string;
  details?: Record<string, any>;
}

export interface ReadyResponse {
  status: string;
  timestamp: string;
  services: {
    postgres: ServiceStatus;
    redis: ServiceStatus;
    qdrant: ServiceStatus;
    neo4j: ServiceStatus;
  };
}
