import { HotelOffer } from '../types/travel';

interface HotelCardProps {
  hotel: HotelOffer;
}

export const HotelCard = ({ hotel }: HotelCardProps) => {
  return (
    <div className="p-4 rounded-xl border border-slate-800 bg-slate-900 hover:border-slate-700 transition-all">
      <div className="flex items-start justify-between">
        <div>
          <h4 className="text-base font-semibold text-white">{hotel.name}</h4>
          <p className="text-xs text-slate-400 mt-0.5">
            📍 {hotel.city} {hotel.address ? `• ${hotel.address}` : ''}
          </p>
        </div>

        <div className="flex items-center space-x-1 px-2 py-0.5 rounded bg-amber-400/10 text-amber-300 border border-amber-400/20 text-xs font-semibold">
          <span>★</span>
          <span>{hotel.star_rating}.0</span>
        </div>
      </div>

      {hotel.amenities && hotel.amenities.length > 0 && (
        <div className="flex flex-wrap gap-1.5 my-3">
          {hotel.amenities.map((am, idx) => (
            <span
              key={idx}
              className="text-[11px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700/60"
            >
              {am}
            </span>
          ))}
        </div>
      )}

      <div className="flex items-center justify-between mt-3 pt-2 border-t border-slate-800/80">
        <div>
          <span className="text-[11px] text-slate-400">Rate per night</span>
          <div className="text-base font-bold text-emerald-400">
            {hotel.currency} {hotel.price_per_night.toLocaleString()}
          </div>
        </div>

        <button className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white transition-colors">
          View Details
        </button>
      </div>
    </div>
  );
};
