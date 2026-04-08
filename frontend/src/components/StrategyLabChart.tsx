import { useEffect, useMemo, useRef } from 'react'
import {
  CandlestickSeries,
  ColorType,
  createChart,
  LineSeries,
  type CandlestickData,
  type IChartApi,
  type ISeriesApi,
  type LineData,
  type Time,
} from 'lightweight-charts'
import type { StrategyLabChartData } from '../types/api'

function toCandle(points: StrategyLabChartData['candles']): CandlestickData[] {
  return points.map((p) => ({
    time: p.time as Time,
    open: p.open,
    high: p.high,
    low: p.low,
    close: p.close,
  }))
}

function toLine(points: StrategyLabChartData['sma_short'] | StrategyLabChartData['sma_long']): LineData[] {
  return points.map((p) => ({
    time: p.time as Time,
    value: p.value,
  }))
}

export function StrategyLabChart({ data }: { data: StrategyLabChartData | null }) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const candleRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const shortRef = useRef<ISeriesApi<'Line'> | null>(null)
  const longRef = useRef<ISeriesApi<'Line'> | null>(null)

  const crossBadge = useMemo(() => {
    if (!data) return '—'
    const buys = data.crosses.filter((c) => c.side === 'buy').length
    const sells = data.crosses.filter((c) => c.side === 'sell').length
    return `${buys} BUY / ${sells} SELL`
  }, [data])

  useEffect(() => {
    if (!containerRef.current || chartRef.current) return
    const chart = createChart(containerRef.current, {
      height: 360,
      layout: {
        background: { type: ColorType.Solid, color: '#0d1117' },
        textColor: '#c9d1d9',
      },
      grid: {
        vertLines: { color: 'rgba(139, 148, 158, 0.12)' },
        horzLines: { color: 'rgba(139, 148, 158, 0.12)' },
      },
      rightPriceScale: { borderColor: '#30363d' },
      timeScale: { borderColor: '#30363d', rightOffset: 8 },
    })
    const candle = chart.addSeries(CandlestickSeries, {
      upColor: '#26a69a',
      downColor: '#ef5350',
      wickUpColor: '#26a69a',
      wickDownColor: '#ef5350',
      borderVisible: false,
    })
    const shortLine = chart.addSeries(LineSeries, {
      color: '#58a6ff',
      lineWidth: 2,
      title: 'SMA short',
    })
    const longLine = chart.addSeries(LineSeries, {
      color: '#d29922',
      lineWidth: 2,
      title: 'SMA long',
    })
    chartRef.current = chart
    candleRef.current = candle
    shortRef.current = shortLine
    longRef.current = longLine

    const onResize = () => {
      if (!containerRef.current || !chartRef.current) return
      chartRef.current.applyOptions({ width: containerRef.current.clientWidth })
    }
    onResize()
    window.addEventListener('resize', onResize)
    return () => {
      window.removeEventListener('resize', onResize)
      chart.remove()
      chartRef.current = null
      candleRef.current = null
      shortRef.current = null
      longRef.current = null
    }
  }, [])

  useEffect(() => {
    if (!data || !candleRef.current || !shortRef.current || !longRef.current || !chartRef.current) return
    candleRef.current.setData(toCandle(data.candles))
    shortRef.current.setData(toLine(data.sma_short))
    longRef.current.setData(toLine(data.sma_long))
    chartRef.current.timeScale().fitContent()
  }, [data])

  return (
    <div className="lab-chart-wrap">
      <h4 className="lab-subtitle">
        Gráfico en vivo · {data?.symbol ?? '—'} · {data?.strategy_name ?? '—'} · {data?.timeframe ?? '—'}
      </h4>
      <p className="chart-meta">
        Cruces detectados (ventana actual): <strong>{crossBadge}</strong>
      </p>
      <div ref={containerRef} className="lab-chart" />
    </div>
  )
}

