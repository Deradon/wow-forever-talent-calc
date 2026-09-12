/** M2: rows by ascending confidence with the frame crop beside the tooltip. */
export function ReviewPage({ classId }: { classId: string }) {
  return (
    <div className="panel p-4">
      <h1 className="serif text-lg text-[var(--gold)]">Review: {classId}</h1>
      <p className="text-[var(--text-dim)]">The review route arrives in milestone M2.</p>
      <a href={`#/${classId}`}>Back to the calculator</a>
    </div>
  )
}
