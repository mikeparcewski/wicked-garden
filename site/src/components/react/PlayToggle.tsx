/** The keyboard pause for a self-playing block. Fixed width, so its label swap never moves a neighbour. */
export default function PlayToggle({
  paused,
  onToggle,
  label,
}: {
  paused: boolean;
  onToggle: () => void;
  /** what plays, for the accessible name: "the gate demo" */
  label: string;
}) {
  return (
    <button
      type="button"
      className="px-play"
      aria-pressed={!paused}
      aria-label={paused ? `Play ${label}` : `Pause ${label}`}
      onClick={onToggle}
    >
      <span className="px-play-ico" aria-hidden>{paused ? "▶" : "❚❚"}</span>
      <span className="px-play-txt">{paused ? "play" : "pause"}</span>
    </button>
  );
}
