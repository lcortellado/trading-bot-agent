/**
 * El API sigue enviando timestamps en UTC (ISO).
 * En la UI los mostramos en hora local de Paraguay para reportes legibles.
 */
export const REPORT_TIMEZONE = 'America/Asuncion'

const reportLocale = 'es-PY'

export function formatReportDateTime(isoOrTs: string): string {
  const d = new Date(isoOrTs)
  if (Number.isNaN(d.getTime())) return isoOrTs
  return d.toLocaleString(reportLocale, {
    timeZone: REPORT_TIMEZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}
