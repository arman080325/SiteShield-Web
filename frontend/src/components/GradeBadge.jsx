const GRADE_STYLES = {
  A: "bg-emerald-500",
  B: "bg-lime-500",
  C: "bg-yellow-500",
  D: "bg-orange-500",
  E: "bg-orange-600",
  F: "bg-red-600",
  "N/A": "bg-zinc-400",

};

export default function GradeBadge({ grade, score }) {
  const color = GRADE_STYLES[grade] || "bg-zinc-500";
  return (
    <div className="flex flex-col items-center">
      <div
        className={`${color} text-white font-bold text-2xl w-14 h-14 rounded-full flex items-center justify-center shadow-md`}
      >
        {grade}
      </div>
      {typeof score === "number" && (
        <span className="text-xs text-zinc-500 mt-1">{score}/100</span>
      )}
    </div>
  );
}