import { MapPinned } from 'lucide-react';

const CAMPUS_ORIGIN =
  import.meta.env.VITE_CAMPUS_ORIGIN?.trim() ||
  'Universitas Klabat, Jl. Arnold Mononutu, Airmadidi Bawah, Kec. Airmadidi, Kabupaten Minahasa Utara, Sulawesi Utara 95371';

export function GoogleMapsDirectionsLink({ destination }: { destination: string }) {
  const normalizedDestination = destination.trim();
  if (!normalizedDestination) return null;

  const query = new URLSearchParams({
    api: '1',
    origin: CAMPUS_ORIGIN,
    destination: normalizedDestination,
    travelmode: 'driving',
  });

  return (
    <div className="space-y-1">
      <a
        href={`https://www.google.com/maps/dir/?${query.toString()}`}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1.5 text-xs font-semibold text-blue-700 underline decoration-blue-300 underline-offset-2 hover:text-blue-900"
      >
        <MapPinned size={14} />
        Lihat rute di Google Maps
      </a>
      <p className="text-[11px] leading-relaxed text-slate-500">
        Alamat dibagikan ke Google Maps saat tautan dibuka. Periksa jarak rute lalu masukkan nilainya secara manual.
      </p>
    </div>
  );
}
