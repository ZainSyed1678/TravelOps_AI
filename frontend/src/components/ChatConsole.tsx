import { useState, useRef, useEffect, ReactNode } from 'react';
import { AgentChatResponse, PendingAction, FlightOffer } from '../types/travel';
import { FlightCard } from './FlightCard';
import { HotelCard } from './HotelCard';
import { TraceViewer } from './TraceViewer';
import { HITLModal } from './HITLModal';

interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  response?: AgentChatResponse;
  timestamp: string;
}

// Lightweight, safe inline Markdown renderer for agent responses
const renderInline = (str: string): ReactNode => {
  const parts: ReactNode[] = [];
  const regex = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g;
  let lastIndex = 0;
  let match;

  while ((match = regex.exec(str)) !== null) {
    if (match.index > lastIndex) {
      parts.push(str.substring(lastIndex, match.index));
    }
    const token = match[0];
    if (token.startsWith('**') && token.endsWith('**')) {
      parts.push(
        <strong key={match.index} className="font-semibold text-white">
          {token.slice(2, -2)}
        </strong>
      );
    } else if (token.startsWith('`') && token.endsWith('`')) {
      parts.push(
        <code key={match.index} className="px-1.5 py-0.5 rounded bg-slate-800 text-sky-300 font-mono text-xs border border-slate-700/60">
          {token.slice(1, -1)}
        </code>
      );
    } else if (token.startsWith('*') && token.endsWith('*')) {
      parts.push(
        <em key={match.index} className="italic text-slate-300">
          {token.slice(1, -1)}
        </em>
      );
    }
    lastIndex = regex.lastIndex;
  }

  if (lastIndex < str.length) {
    parts.push(str.substring(lastIndex));
  }

  return parts.length > 0 ? parts : str;
};

const FormattedMessage = ({ text }: { text: string }) => {
  if (!text) return null;
  const lines = text.split('\n');

  return (
    <div className="space-y-1.5 leading-relaxed text-sm">
      {lines.map((line, lIdx) => {
        const trimmed = line.trim();
        if (!trimmed) {
          return <div key={lIdx} className="h-1.5" />;
        }

        // Heading 3 / Section: ### Heading
        if (trimmed.startsWith('### ')) {
          return (
            <h4 key={lIdx} className="text-sm font-bold text-sky-300 mt-2 mb-1">
              {renderInline(trimmed.slice(4))}
            </h4>
          );
        }

        // Blockquote / Safety alert
        if (trimmed.startsWith('> ')) {
          return (
            <div key={lIdx} className="border-l-2 border-amber-500 pl-2.5 py-1 my-1.5 text-xs text-amber-200/90 italic bg-amber-950/20 rounded-r">
              {renderInline(trimmed.slice(2))}
            </div>
          );
        }

        // Bullet item: - item or * item
        if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
          return (
            <div key={lIdx} className="flex items-start space-x-2 text-xs text-slate-300 ml-1">
              <span className="text-sky-400 select-none">•</span>
              <span>{renderInline(trimmed.slice(2))}</span>
            </div>
          );
        }

        return (
          <p key={lIdx} className="text-slate-200">
            {renderInline(line)}
          </p>
        );
      })}
    </div>
  );
};

export const ChatConsole = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      sender: 'assistant',
      text: 'Hello! I am your TravelOps AI Operations Assistant. I can search flights, explain airline fare rules & cancellation policies, handle flight disruptions, and recommend hotels.',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ]);
  const [inputQuery, setInputQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [activeHITLAction, setActiveHITLAction] = useState<PendingAction | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    try {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    } catch {
      // Ignore if DOM ref not attached
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const sendMessage = async (queryText: string) => {
    const trimmed = queryText.trim();
    if (!trimmed || loading) return;

    const userMsg: ChatMessage = {
      id: `usr_${Date.now()}`,
      sender: 'user',
      text: trimmed,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputQuery('');
    setLoading(true);

    try {
      const res = await fetch('/api/v1/agents/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: trimmed,
          thread_id: threadId,
        }),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `API error: ${res.statusText}`);
      }

      const data: AgentChatResponse = await res.json();
      if (data.thread_id) {
        setThreadId(data.thread_id);
      }

      const assistantMsg: ChatMessage = {
        id: `asst_${Date.now()}`,
        sender: 'assistant',
        text: data.response_message || 'Processing complete.',
        response: data,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      setMessages((prev) => [...prev, assistantMsg]);

      // If action requires confirmation, notify operator
      if (data.requires_human_confirmation && data.pending_action) {
        setActiveHITLAction(data.pending_action);
      }
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        id: `err_${Date.now()}`,
        sender: 'assistant',
        text: `Error processing request: ${err.message || 'Unknown network error'}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectFlight = (flight: FlightOffer) => {
    const f = (flight as any).offer || flight;
    const airline = f.airline_code || '';
    const num = f.flight_number || '';
    const curr = f.currency || 'INR';
    const price = f.total_price != null ? f.total_price : '';
    sendMessage(`I want to book flight ${airline}${num} for ${curr} ${price}`);
  };

  const quickPrompts = [
    { label: '✈️ Flights BOM → DXB', query: 'Find the cheapest flights from Mumbai to Dubai next Tuesday' },
    { label: '📋 Air India Policy', query: 'What are the baggage allowance rules and cancellation fees for Air India?' },
    { label: '⚠️ Disruption Rebooking', query: 'Flight EK505 is delayed by 4 hours. Can I rebook reservation BK-EK505-001?' },
    { label: '🏨 Dubai Marina Hotels', query: 'Recommend 4 star hotels in Dubai near the marina' },
  ];

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)] bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-2xl">
      {/* Header bar */}
      <div className="px-6 py-3.5 bg-slate-950/90 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse"></div>
          <span className="text-sm font-semibold text-white">LangGraph Agent Session</span>
          {threadId && (
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-slate-800 text-slate-300 font-mono border border-slate-700/60">
              Thread: {threadId}
            </span>
          )}
        </div>

        <button
          onClick={() => {
            setThreadId(null);
            setMessages([messages[0]]);
          }}
          className="text-xs px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700/60 transition-colors"
        >
          New Conversation
        </button>
      </div>

      {/* Messages timeline */}
      <div className="flex-1 overflow-y-auto p-6 space-y-5">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex flex-col ${msg.sender === 'user' ? 'items-end' : 'items-start'}`}
          >
            <div className="flex items-center space-x-2 mb-1 px-1">
              <span className="text-[11px] font-semibold text-slate-400">
                {msg.sender === 'user' ? 'Operator' : 'TravelOps AI'}
              </span>
              <span className="text-[10px] text-slate-500 font-mono">{msg.timestamp}</span>
              {msg.response?.workflow && (
                <span className="text-[10px] px-2 py-0.5 rounded-full font-mono bg-sky-950 text-sky-400 border border-sky-800">
                  {msg.response.workflow}
                </span>
              )}
            </div>

            <div
              className={`max-w-3xl rounded-2xl p-4 text-sm ${
                msg.sender === 'user'
                  ? 'bg-sky-600 text-white rounded-br-none shadow-md shadow-sky-900/40'
                  : 'bg-slate-950 text-slate-200 border border-slate-800 rounded-bl-none shadow-sm'
              }`}
            >
              {/* Formatted message content */}
              <FormattedMessage text={msg.text} />

              {/* RAG Citations */}
              {msg.response?.policy_response?.sources && msg.response.policy_response.sources.length > 0 && (
                <div className="mt-4 pt-3 border-t border-slate-800/80">
                  <div className="text-xs font-semibold text-sky-400 mb-2 flex items-center space-x-1.5">
                    <span>📚</span>
                    <span>Grounded Policy Provenance ({msg.response.policy_response.sources.length} sources):</span>
                  </div>
                  <div className="space-y-2">
                    {msg.response.policy_response.sources.map((cit, idx) => {
                      const score = cit.relevance_score != null ? Math.round(cit.relevance_score * 100) : 0;
                      return (
                        <div
                          key={idx}
                          className="p-2.5 rounded-lg bg-slate-900/90 border border-slate-800 text-xs space-y-1"
                        >
                          <div className="flex items-center justify-between text-slate-300 font-medium">
                            <span>📄 {cit.document || 'Travel Policy'} {cit.section ? `• ${cit.section}` : ''}</span>
                            <span className="text-[11px] font-mono text-emerald-400">
                              {score}% relevance
                            </span>
                          </div>
                          {cit.snippet && (
                            <p className="text-slate-400 text-[11px] italic">"{cit.snippet}"</p>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Flight Search Results */}
              {msg.response?.flight_results && msg.response.flight_results.length > 0 && (
                <div className="mt-4 pt-3 border-t border-slate-800/80">
                  <div className="text-xs font-semibold text-emerald-400 mb-2 flex items-center space-x-1.5">
                    <span>✈️</span>
                    <span>Ranked Flight Offers ({msg.response.flight_results.length} available):</span>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {msg.response.flight_results.map((f: any, idx: number) => {
                      const offerId = f?.offer?.offer_id || f?.offer_id || `flt_${idx}`;
                      return (
                        <FlightCard key={offerId} flight={f} onSelect={handleSelectFlight} />
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Hotel Discovery Results */}
              {msg.response?.hotel_results && msg.response.hotel_results.length > 0 && (
                <div className="mt-4 pt-3 border-t border-slate-800/80">
                  <div className="text-xs font-semibold text-indigo-400 mb-2 flex items-center space-x-1.5">
                    <span>🏨</span>
                    <span>Recommended Properties ({msg.response.hotel_results.length} hotels):</span>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {msg.response.hotel_results.map((h: any, idx: number) => {
                      const hotelId = h?.hotel?.hotel_id || h?.hotel_id || `htl_${idx}`;
                      return (
                        <HotelCard key={hotelId} hotel={h} />
                      );
                    })}
                  </div>
                </div>
              )}

              {/* HITL Safety Banner */}
              {msg.response?.requires_human_confirmation && msg.response?.pending_action && (
                <div className="mt-4 p-3.5 rounded-xl bg-amber-950/40 border border-amber-600/60 flex items-center justify-between gap-3">
                  <div>
                    <div className="flex items-center space-x-1.5 text-amber-300 font-bold text-xs">
                      <span>⚠️ High-Risk Action Proposal</span>
                      <span className="px-1.5 py-0.5 rounded bg-red-950 text-red-400 border border-red-800 font-mono text-[10px] uppercase">
                        {msg.response.pending_action.risk_level || 'HIGH'}
                      </span>
                    </div>
                    <p className="text-xs text-slate-300 mt-1">
                      {msg.response.pending_action.description || 'This mutating action requires human confirmation before execution.'}
                    </p>
                  </div>
                  <button
                    onClick={() => setActiveHITLAction(msg.response!.pending_action!)}
                    className="px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-amber-600 hover:bg-amber-500 text-white transition-colors whitespace-nowrap shadow-md shadow-amber-950/40"
                  >
                    Review & Decide
                  </button>
                </div>
              )}

              {/* Execution Trace */}
              {msg.response?.trace && Array.isArray(msg.response.trace) && msg.response.trace.length > 0 && (
                <TraceViewer trace={msg.response.trace} workflow={msg.response.workflow || 'AGENT'} />
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex items-center space-x-2 text-slate-400 text-xs p-3 rounded-xl bg-slate-950/60 border border-slate-800/60 w-fit">
            <div className="w-2 h-2 rounded-full bg-sky-400 animate-ping"></div>
            <span>TravelOps Agent coordinating state machine across Search, RAG & ML...</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Quick Prompts Bar */}
      <div className="px-6 py-2.5 bg-slate-950/70 border-t border-slate-800/80 flex items-center space-x-2 overflow-x-auto">
        <span className="text-xs text-slate-500 font-medium whitespace-nowrap">Suggested:</span>
        {quickPrompts.map((qp, idx) => (
          <button
            key={idx}
            onClick={() => sendMessage(qp.query)}
            disabled={loading}
            className="text-xs px-3 py-1 rounded-full bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700/60 whitespace-nowrap transition-colors disabled:opacity-50"
          >
            {qp.label}
          </button>
        ))}
      </div>

      {/* Input area */}
      <div className="p-4 bg-slate-950 border-t border-slate-800">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            sendMessage(inputQuery);
          }}
          className="flex space-x-3"
        >
          <input
            type="text"
            value={inputQuery}
            onChange={(e) => setInputQuery(e.target.value)}
            placeholder="Type a travel instruction e.g. 'Search flights Mumbai to Dubai' or 'Air India baggage policy'..."
            disabled={loading}
            className="flex-1 px-4 py-3 bg-slate-900 border border-slate-800 rounded-xl text-sm text-white placeholder-slate-500 focus:outline-none focus:border-sky-500 transition-colors"
          />

          <button
            type="submit"
            disabled={loading || !inputQuery.trim()}
            className="px-6 py-3 rounded-xl font-semibold text-sm bg-sky-600 hover:bg-sky-500 text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-md shadow-sky-900/40"
          >
            Send
          </button>
        </form>
      </div>

      {/* Active HITL Modal */}
      {activeHITLAction && (
        <HITLModal
          action={activeHITLAction}
          onClose={() => setActiveHITLAction(null)}
          onActionComplete={(updated) => {
            setMessages((prev) => [
              ...prev,
              {
                id: `act_${Date.now()}`,
                sender: 'assistant',
                text: `Action ${updated.action_id || ''} (${updated.action_type || 'MUTATION'}) marked as ${updated.status || 'PROCESSED'}. Operator notes: ${updated.operator_notes || 'None'}`,
                timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
              },
            ]);
          }}
        />
      )}
    </div>
  );
};
