// SakoMap.jsx — rend la carte des flux Sako à partir de diaspora-map.data.json.
// Aucune dépendance (ni carto ni animation JS) : tout est déjà projeté dans le
// JSON, l'animation est en CSS. Thème clair, responsive, prêt pour landing page.
//
//   import SakoMap from "./SakoMap";
//   <SakoMap />                       // utilise le JSON importé par défaut
//   <SakoMap data={monJson} />        // ou fournir ses propres données
//
// Le JSON et sako-map.css doivent être servis à côté de ce fichier.
import data from "../diaspora-map.data.json";
import "./sako-map.css";

export default function SakoMap({ data: d = data }) {
  const vb = d.viewBox;
  const flowStyle = (f) => ({ "--dur": `${f.durationSec}s`, "--delay": `${f.delaySec}s` });

  return (
    <div className="sako-map">
      <div className="sako-mapfield">
        <div className="sako-scroll">
          <svg
            className="sako-svg"
            viewBox={`0 0 ${vb.width} ${vb.height}`}
            preserveAspectRatio="xMidYMid meet"
            role="img"
            aria-label="Carte des transferts Sako : la diaspora envoie vers 11 pays d'Afrique de l'Ouest et centrale, dont le Ghana."
          >
            <defs>
              <filter id="sk-glow" x="-40%" y="-40%" width="180%" height="180%">
                <feGaussianBlur stdDeviation="4" result="b" />
                <feMerge>
                  <feMergeNode in="b" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>

            {/* pays d'arrière-plan */}
            <g className="sk-bg">
              {d.background.map((p, i) => (
                <path key={i} d={p} />
              ))}
            </g>

            {/* pays desservis */}
            <g className="sk-hi">
              {d.served.map((s) => (
                <path key={s.iso} className="sk-country" d={s.path} />
              ))}
            </g>

            {/* flux : tracé guide + comète (queue + cœur) */}
            <g className="sk-arcs">
              {d.flows.map((f, i) => (
                <g key={i}>
                  <path className="sk-guide" d={f.path} pathLength="1" />
                  <path className="sk-flow sk-flow-tail" d={f.path} pathLength="1" style={flowStyle(f)} />
                  <path className="sk-flow sk-flow-core" d={f.path} pathLength="1" style={flowStyle(f)} />
                </g>
              ))}
            </g>

            {/* réception : halo d'arrivée + marqueur */}
            <g className="sk-dests">
              {d.flows.map((f, i) => (
                <g key={i}>
                  <circle className="sk-land-pulse" cx={f.arrival.x} cy={f.arrival.y} r="10" style={flowStyle(f)} />
                  <circle className="sk-dest-ring" cx={f.arrival.x} cy={f.arrival.y} r="9" />
                  <circle className="sk-dest-dot" cx={f.arrival.x} cy={f.arrival.y} r="4.2" />
                </g>
              ))}
            </g>

            {/* villes d'envoi */}
            <g className="sk-origins">
              {d.origins.map((o, i) => (
                <g key={i}>
                  <circle className="sk-origin-breathe" cx={o.x} cy={o.y} r="7" />
                  <circle className="sk-origin-dot" cx={o.x} cy={o.y} r="5" />
                </g>
              ))}
            </g>

            {/* lignes de rappel (petits pays côtiers) */}
            <g className="sk-leaders">
              {d.served.filter((s) => s.leader).map((s) => (
                <g key={s.iso}>
                  <line className="sk-leader" x1={s.leader.x1} y1={s.leader.y1} x2={s.leader.x2} y2={s.leader.y2} />
                  <circle className="sk-leader-dot" cx={s.leader.x2} cy={s.leader.y2} r="3" />
                </g>
              ))}
            </g>

            {/* libellés des villes */}
            <g className="sk-city-labels">
              {d.origins.map((o, i) => (
                <text key={i} className="sk-city" x={o.label.x} y={o.label.y} textAnchor={o.label.anchor}>
                  {o.name}
                </text>
              ))}
            </g>

            {/* libellés des pays */}
            <g className="sk-country-labels">
              {d.served.map((s) => (
                <text
                  key={s.iso}
                  className={"sk-clabel" + (s.label.small ? " sk-small" : "") + (s.iso === "GHA" ? " sk-gha" : "")}
                  x={s.label.x}
                  y={s.label.y}
                  textAnchor={s.label.anchor}
                >
                  {s.name}
                </text>
              ))}
            </g>
          </svg>
          <div className="sako-fade" />
        </div>
      </div>
    </div>
  );
}
