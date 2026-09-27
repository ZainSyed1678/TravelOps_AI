import { FlightOffer } from '../types/travel';

interface FlightCardProps {
  flight: FlightOffer | any;
  onSelect?: (flight: FlightOffer) => void;
}

export const FlightCard = ({ flight: rawFlight, onSelect }: FlightCardProps) => {
  if (!rawFlight) return null;

  // Support both flattened FlightOffer and nested { offer: FlightOffer, rank, score }
  const offer = rawFlight.offer || rawFlight;
  const rank = rawFlight.rank ?? offer.rank;
  const score = rawFlight.score ?? offer.score;
  const isTopRanked = rank === 1;

  const origin = offer.origin || '---';
  const destination = offer.destination || '---';
  const airlineCode = offer.airline_code || '';
  const flightNumber = offer.flight_number || '';
  const airlineName = offer.airline_name || airlineCode || 'Flight';
  const cabinClass = offer.cabin_class || 'ECONOMY';
  const currency = offer.currency || 'INR';
  const price = offer.total_price != null ? Number(offer.total_price).toLocaleString() : 'N/A';
  const stops = offer.stops ?? 0;

  const formatTime = (iso?: string) => {
    if (!iso) return '--:--';
    const d = new Date(iso);
    return isNaN(d.getTime()) ? iso : d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const depTime = formatTime(offer.departure_time);
  const arrTime = formatTime(offer.arrival_time);

  const durationMins = typeof offer.duration_minutes === 'number' ? offer.duration_minutes : 0;
  const durationText = durationMins > 0 ? `${Math.floor(durationMins / 60)}h ${durationMins % 60}m` : 'Direct';

  return (
    <div
      className={`p-4 rounded-xl border transition-all ${
        isTopRanked
          ? 'bg-gradient-to-br from-slate-900 via-sky-950/30 to-slate-900 border-sky-500 shadow-lg shadow-sky-950/50'
          : 'bg-slate-900/90 border-slate-800 hover:border-slate-700 shadow-sm'
      }`}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-2">
          <span className="text-xs font-semibold px-2 py-0.5 rounded bg-slate-800 text-sky-300 border border-slate-700 font-mono">
            {airlineCode} {flightNumber}
          </span>
          <span className="text-sm font-medium text-slate-200">{airlineName}</span>
        </div>

        {rank !== undefined && (
          <div className="flex items-center space-x-1.5">
            <span
              className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                isTopRanked
                  ? 'bg-amber-400/20 text-amber-300 border border-amber-400/40'
                  : 'bg-slate-800 text-slate-300 border border-slate-700'
              }`}
            >
              Rank #{rank}
            </span>
            {score !== undefined && (
              <span className="text-xs text-slate-400 font-mono">
                ({Math.round(score * 100)}% match)
              </span>
            )}
          </div>
        )}
      </div>

      <div className="grid grid-cols-3 items-center py-2.5 border-y border-slate-800/80 my-2 text-center">
        <div className="text-left">
          <div className="text-lg font-bold text-white tracking-wide">{origin}</div>
          <div className="text-xs text-slate-400 font-mono">{depTime}</div>
        </div>

        <div className="text-center px-1">
          <div className="text-xs text-slate-400 font-mono">{durationText}</div>
          <div className="relative flex items-center justify-center my-1">
            <div className="w-full border-t border-dashed border-slate-600"></div>
            <span className="text-[10px] px-1.5 py-0.2 absolute bg-slate-900 text-slate-400 rounded border border-slate-800">
              {stops === 0 ? 'Direct' : `${stops} stop`}
            </span>
          </div>
          <div className="text-[10px] text-slate-500 uppercase font-semibold">{cabinClass}</div>
        </div>

        <div className="text-right">
          <div className="text-lg font-bold text-white tracking-wide">{destination}</div>
          <div className="text-xs text-slate-400 font-mono">{arrTime}</div>
        </div>
      </div>

      <div className="flex items-center justify-between mt-3 pt-1">
        <div>
          <span className="text-[11px] text-slate-400 block">Total Price</span>
          <div className="text-lg font-bold text-emerald-400 font-mono">
            {currency} {price}
          </div>
        </div>

        {onSelect && (
          <button
            onClick={() => onSelect(offer)}
            className="px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-sky-600 hover:bg-sky-500 text-white transition-all shadow-sm shadow-sky-900/30"
          >
            Select Offer
          </button>
        )}
      </div>
    </div>
  );
};
