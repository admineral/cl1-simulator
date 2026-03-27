"use client";

export type ControlPlaneLogEntry = {
  id: string;
  timeUtc: string;
  message: string;
};

type Props = {
  entries: ControlPlaneLogEntry[];
};

export function Cl1ControlPlaneLog({ entries }: Props) {
  return (
    <div className="cl1-cplog" aria-label="Control plane events">
      <div className="cl1-cplog__head">Control plane</div>
      <ul className="cl1-cplog__list">
        {entries.length === 0 ? (
          <li className="cl1-cplog__empty">No events yet · start loop or queue stim</li>
        ) : (
          entries.map((e) => (
            <li key={e.id} className="cl1-cplog__row">
              <span className="cl1-cplog__t">{e.timeUtc}</span>
              <span className="cl1-cplog__m">{e.message}</span>
            </li>
          ))
        )}
      </ul>
    </div>
  );
}
