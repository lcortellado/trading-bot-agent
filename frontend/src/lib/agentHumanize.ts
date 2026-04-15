/**
 * Textos en lenguaje cotidiano (es) para decisiones del agente y analistas.
 * Los datos crudos siguen viniendo del API en inglés técnico.
 */

export function decisionLabelEs(decision: string | null | undefined): string {
  if (decision === 'ENTER') return 'Entrar (operar)'
  if (decision === 'SKIP') return 'No operar'
  if (decision === 'REDUCE_SIZE') return 'Operar en menor tamaño'
  return 'Sin decisión'
}

export function stanceLabelEs(stance: string | undefined): string {
  const s = (stance ?? 'neutral').toLowerCase()
  if (s === 'bullish') return 'Alcista'
  if (s === 'bearish') return 'Bajista'
  if (s === 'mixed') return 'Contradictorio (hay señales encontradas)'
  return 'Neutral'
}

/** Una frase que explica el “score” sin números técnicos. */
export function scorePlainEs(score: number, stance: string): string {
  const s = (stance ?? '').toLowerCase()
  const abs = Math.abs(score)
  let fuerza = 'levemente'
  if (abs > 0.65) fuerza = 'claramente'
  else if (abs > 0.35) fuerza = 'moderadamente'

  if (s === 'mixed') {
    return 'Las fuentes que miramos no coinciden del todo entre sí.'
  }
  if (s === 'bullish') {
    return `En conjunto, las lecturas apuntan ${fuerza} hacia precios más altos.`
  }
  if (s === 'bearish') {
    return `En conjunto, las lecturas apuntan ${fuerza} hacia precios más bajos.`
  }
  if (abs < 0.12) {
    return 'No hay un sesgo fuerte ni hacia arriba ni hacia abajo.'
  }
  return 'El panorama está bastante equilibrado.'
}

/** Qué tan “claro” fue el análisis para ese bloque (no es probabilidad de ganar). */
export function analystConfidencePlainEs(confidence: number): string {
  if (confidence >= 0.75) return 'El contexto que tuvo este bloque era bastante claro.'
  if (confidence >= 0.45) return 'El contexto era razonable, pero no muy contundente.'
  return 'Había poca información firme para este bloque.'
}

export function analystTitleEs(analystId: string): string {
  if (analystId === 'signal_consensus') return '¿Qué dicen las señales del bot?'
  if (analystId === 'market_context') return '¿Cómo está el mercado (volumen y tendencia)?'
  if (analystId === 'news_digest') return '¿Qué tono tienen los titulares de noticias?'
  return analystId.replace(/_/g, ' ')
}

export function analystSubtitleEs(analystId: string): string {
  if (analystId === 'signal_consensus') {
    return 'Resume si tus indicadores piden comprar, vender o esperar, y si se pelean entre sí.'
  }
  if (analystId === 'market_context') {
    return 'Usa solo datos que ya enviaste (tendencia, volatilidad, volumen). No adivina el futuro.'
  }
  if (analystId === 'news_digest') {
    return 'Palabras clave en titulares (no lee internet en vivo). Sirve como ambiente, no como verdad absoluta.'
  }
  return ''
}

/** Convierte líneas técnicas del backend a español coloquial. */
export function humanizeDriverLine(raw: string): string {
  let t = raw.trim()
  if (!t) return t

  if (t === 'No strategy signals in bundle') {
    return 'No llegaron señales de estrategia en esta petición.'
  }
  if (t === 'No market_context fields set') {
    return 'No se indicó contexto extra de mercado (tendencia, volumen, etc.).'
  }
  if (t === 'No headlines ingested for this symbol') {
    return 'No hay titulares de noticias cargados para este par (o están desactivados).'
  }

  const mCount = /^(\d+) buy \/ (\d+) sell \/ (\d+) hold among (\d+) signals$/.exec(t)
  if (mCount) {
    const [, buy, sell, hold, total] = mCount
    return `Resumen rápido: ${buy} señales de compra, ${sell} de venta, ${hold} de “esperar”, de un total de ${total}.`
  }

  if (t.startsWith('lexicon hits:')) {
    const m = /bullish=(\d+), bearish=(\d+) across (\d+) headlines/.exec(t)
    if (m) {
      const [, bull, bear, n] = m
      return `En ${n} titular(es), el tono automático vio más matices “positivos” (${bull}) que “negativos” (${bear}) en el texto (muy aproximado).`
    }
  }

  if (t.startsWith('risk-tone hits:')) {
    const n = t.replace(/^risk-tone hits:\s*/i, '').trim()
    return `Aparecen ${n} indicios de tono de riesgo o incertidumbre en los titulares.`
  }

  if (t.startsWith('sample:')) {
    const inner = t.replace(/^sample:\s*/i, '').replace(/^['"]|['"]$/g, '')
    return `Ejemplo de titular: ${inner}`
  }

  if (t.includes('headline(s); no lexicon hits')) {
    return 'Hay titulares, pero sin palabras típicas “alcistas/bajistas” en el resumen automático (puede ser noticia neutra o macro).'
  }

  if (t === 'trend labeled bullish') return 'La tendencia indicada es alcista.'
  if (t === 'trend labeled bearish') return 'La tendencia indicada es bajista.'
  if (t === 'trend labeled sideways') return 'La tendencia indicada es lateral (sin rumbo claro).'

  const volEl = /^elevated 24h volatility \(~([\d.]+)%\)$/.exec(t)
  if (volEl) return `Volatilidad de 24 h alta (aprox. ${volEl[1]}%): el precio se ha movido bastante.`
  const volCo = /^compressed 24h volatility \(~([\d.]+)%\)$/.exec(t)
  if (volCo) return `Volatilidad de 24 h baja (aprox. ${volCo[1]}%): el precio se ha movido poco.`

  const vrAbove = /^volume_ratio ([\d.]+) \(above average\)$/.exec(t)
  if (vrAbove) return `El volumen ronda un ${vrAbove[1]}× respecto a lo habitual: más actividad que el promedio.`
  const vrBelow = /^volume_ratio ([\d.]+) \(below average\)$/.exec(t)
  if (vrBelow) return `El volumen ronda un ${vrBelow[1]}× respecto a lo habitual: menos actividad que el promedio.`

  const strat = /^([^:]+):\s*(buy|sell|hold)\s*\(([\d.]+)%\)$/i.exec(t)
  if (strat) {
    const [, name, act, pct] = strat
    const actEs = act.toLowerCase() === 'buy' ? 'comprar' : act.toLowerCase() === 'sell' ? 'vender' : 'esperar'
    return `“${name}” sugiere ${actEs}, con confianza declarada del ${pct}%.`
  }

  return t
}
