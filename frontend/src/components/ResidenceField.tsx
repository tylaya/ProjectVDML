import { useId } from 'react';

export const HOME_NAME_OPTION = 'Rumah pribadi/keluarga';
export const HOME_ADDRESS_OPTION = 'Area rumah (tanpa alamat rinci)';

export function ResidenceField({ label, value, options, onChange }: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  const listId = useId();
  const choices = [...new Set(options.filter(Boolean))];

  return <label className="text-xs font-medium text-slate-600">{label}
    <input required list={listId} value={value} onChange={event => onChange(event.target.value)} placeholder="Pilih atau ketik..." className="mt-1 w-full rounded-lg border px-3 py-2 text-sm" />
    <datalist id={listId}>{choices.map(option => <option key={option} value={option} />)}</datalist>
  </label>;
}
