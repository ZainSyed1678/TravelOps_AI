import { FlightOffer } from '../types/travel';

interface FlightCardProps {
  flight: FlightOffer;
  onSelect?: (flight: FlightOffer) => void;
}

export const FlightCard = ({ flight, onSelect }: FlightCardProps) => {
  const isTopRanked = flight.rank === 1;

  return (
    <div
      className={`p-4 rounded-xl border transition-all ${
        isTopRanked
          ? 'bg-gradient-to-br from-slate-900 via-sky-950/30 to-slate-900 border-sky-500 shadow-md shadow-sky-950/50'
          : 'bg-slate-900 border-slate-800 hover:border-slate-700'
      }`}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-2">
          <span className="text-xs font-semibold px-2 py-0.5 rounded bg-slate-800 text-sky-300 border border-slate-700">
            {flight.airline_code} {flight.flight_number}
          </span>
          <span className="text-sm font-medium text-slate-200">{flight.airline_name}</span>
        </div>

        {flight.rank !== undefined && (
          <div className="flex items-center space-x-1.5">
            <span
              className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                isTopRanked
                  ? 'bg-amber-400/20 text-amber-300 border border-amber-400/40'
                  : 'bg-slate-800 text-slate-300 border border-slate-700'
              }`}
            >
              Rank #{flight.rank}
            </span>
            {flight.score !== undefined && (
              <span className="text-xs text-slate-400 font-mono">
                ({Math.round(flight.score * 100)}% match)
              </span>
            )}
          </div>
        )}
      </div>

      <div className="grid grid-cols-3 items-center py-2 border-y border-slate-800/80 my-2 text-center">
        <div className="text-left">
          <div className="text-lg font-bold text-white">{flight.origin}</div>
          <div className="text-xs text-slate-400">
            {new Date(flight.departure_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </div>
        </div>

        <div className="text-center">
          <div className="text-xs text-slate-400">
            {Math.floor(flight.duration_minutes / 60)}h {flight.duration_minutes % 60}m
          </div>
          <div className="relative flex items-center justify-center my-1">
            <div className="w-full border-t border-dashed border-slate-600"></div>
            <span className="text-xs px-1 absolute bg-slate-900 text-slate-400">
              {flight.stops === 0 ? 'Direct' : `${flight.stops} stop`}
            </span>
          </div>
          <div className="text-[10px] text-slate-500 uppercase">{flight.cabin_class}</div>
        </div>

        <div className="text-right">
          <div className="text-lg font-bold text-white">{flight.destination}</div>
          <div className="text-xs text-slate-400">
            {new Date(flight.arrival_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between mt-3 pt-1">
        <div>
          <span className="text-xs text-slate-400">Total Price</span>
          <div className="text-lg font-bold text-emerald-400">
            {flight.currency} {flight.total_price.toLocaleString()}
          </div>
        </div>

        {onSelect && (
          <button
            onClick={() => onSelect(flight)}
            className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-sky-600 hover:bg-sky-500 text-white transition-colors"
          >
            Select Offer
          </button>
        )}
      </div>
    </div>
  );
};
