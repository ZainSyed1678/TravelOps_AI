import { HotelOffer } from '../types/travel';

interface HotelCardProps {
  hotel: HotelOffer | any;
}

export const HotelCard = ({ hotel: rawHotel }: HotelCardProps) => {
  if (!rawHotel) return null;

  const hotel = rawHotel.hotel || rawHotel;
  const name = hotel.name || 'Hotel Property';
  const city = hotel.city || '';
  const address = hotel.address || '';
  const starRating = hotel.star_rating != null ? Number(hotel.star_rating).toFixed(1) : '4.0';
  const currency = hotel.currency || 'INR';
  const price = hotel.price_per_night != null ? Number(hotel.price_per_night).toLocaleString() : 'N/A';
  const amenities = Array.isArray(hotel.amenities) ? hotel.amenities : [];

  return (
    <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/90 hover:border-slate-700 transition-all shadow-sm">
      <div className="flex items-start justify-between">
        <div>
          <h4 className="text-base font-semibold text-white tracking-wide">{name}</h4>
          <p className="text-xs text-slate-400 mt-0.5">
            📍 {city} {address ? `• ${address}` : ''}
          </p>
        </div>

        <div className="flex items-center space-x-1 px-2 py-0.5 rounded bg-amber-400/10 text-amber-300 border border-amber-400/20 text-xs font-semibold">
          <span>★</span>
          <span>{starRating}</span>
        </div>
      </div>

      {amenities.length > 0 && (
        <div className="flex flex-wrap gap-1.5 my-3">
          {amenities.map((am: string, idx: number) => (
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
          <span className="text-[11px] text-slate-400 block">Rate per night</span>
          <div className="text-base font-bold text-emerald-400 font-mono">
            {currency} {price}
          </div>
        </div>

        <button className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white transition-all shadow-sm shadow-indigo-900/30">
          View Details
        </button>
      </div>
    </div>
  );
};
