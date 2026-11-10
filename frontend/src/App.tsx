import { useEffect, useState } from 'react'
import './App.css'

const API_URL = import.meta.env.DEV
  ? 'http://127.0.0.1:8080'
  : 'https://llm-analytics-api-zghvsfuxiq-ew.a.run.app'
type Breakdown = { name: string; request_count: number; total_cost_usd: number }
type Analytics = { summary: { request_count: number; total_cost_usd: number; input_tokens: number; output_tokens: number; average_latency_ms: number; successful_requests: number; failed_requests: number }; by_provider: Breakdown[]; by_model: Breakdown[] }
const TIMEFRAMES = [
  { value: 'all', label: 'All time' },
  { value: '7', label: 'Last 7 days' },
  { value: '30', label: 'Last 30 days' },
  { value: '90', label: 'Last 90 days' },
] as const
type Timeframe = (typeof TIMEFRAMES)[number]['value']
const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 })
const compact = new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 })

function isTimeframe(value: string): value is Timeframe {
  return TIMEFRAMES.some((timeframe) => timeframe.value === value)
}

function App() {
  const [data, setData] = useState<Analytics | null>(null)
  const [error, setError] = useState('')
  const [timeframe, setTimeframe] = useState<Timeframe>('all')

  useEffect(() => {
    const controller = new AbortController()
    const params = new URLSearchParams()
    if (timeframe !== 'all') params.set('days', timeframe)
    const query = params.toString()
    const url = query ? `${API_URL}?${query}` : API_URL

    fetch(url, { signal: controller.signal }).then((response) => {
      if (!response.ok) throw new Error('The analytics API is unavailable.')
      return response.json() as Promise<Analytics>
    }).then(setData).catch((requestError: Error) => {
      if (requestError.name !== 'AbortError') setError(requestError.message)
    })

    return () => controller.abort()
  }, [timeframe])

  const handleTimeframeChange = (value: Timeframe) => {
    setData(null)
    setError('')
    setTimeframe(value)
  }

  return (
    <main className="shell"><header className="topbar"><a className="brand" href="#top"><span className="brand-mark">λ</span><span>LLM Cost <strong>Analytics</strong></span></a><div className="live-status"><span /> LIVE DATA <small>GCP / BigQuery</small></div></header>
      <section className="hero" id="top"><div><p className="eyebrow">OPERATIONS CONSOLE / 01</p><h1>Know what your<br /><em>models cost.</em></h1><p className="hero-copy">A clear view of LLM activity, latency, and spend across your production-like workload.</p></div><div className="hero-orbit" aria-hidden="true"><div className="orbit-ring" /><div className="orbit-core">$</div></div></section>
      {error && <div className="error-banner">Could not connect to analytics API: {error}</div>}
      {!data && !error && <div className="loading">Loading warehouse telemetry<span>...</span></div>}
      {data && <Dashboard data={data} timeframe={timeframe} onTimeframeChange={handleTimeframeChange} />}
      <footer><span>LLM COST ANALYTICS PIPELINE</span><span>Cloud Storage → Functions → BigQuery → React</span></footer></main>
  )
}

function Dashboard({ data, timeframe, onTimeframeChange }: { data: Analytics; timeframe: Timeframe; onTimeframeChange: (value: Timeframe) => void }) { const { summary } = data; const successRate = summary.request_count ? (summary.successful_requests / summary.request_count) * 100 : 0; const totalProviderCost = data.by_provider.reduce((total, item) => total + item.total_cost_usd, 0); return <><div className="dashboard-controls"><span className="scope-label">LIVE WAREHOUSE SCOPE</span><label>Timeframe <select value={timeframe} onChange={(event) => { const value = event.currentTarget.value; if (isTimeframe(value)) onTimeframeChange(value) }}>{TIMEFRAMES.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label></div><section className="kpi-grid" aria-label="Key metrics"><Metric label="Total spend" value={money.format(summary.total_cost_usd)} accent /><Metric label="Requests processed" value={compact.format(summary.request_count)} detail={`${summary.successful_requests.toLocaleString()} successful`} /><Metric label="Average latency" value={`${Math.round(summary.average_latency_ms)} ms`} detail={`${successRate.toFixed(1)}% success rate`} /><Metric label="Tokens consumed" value={compact.format(summary.input_tokens + summary.output_tokens)} detail={`${compact.format(summary.input_tokens)} in / ${compact.format(summary.output_tokens)} out`} /></section><section className="analysis-grid"><article className="panel"><div className="panel-heading"><div><p className="eyebrow">SPEND DISTRIBUTION</p><h2>By provider</h2></div><span className="panel-note">USD</span></div><div className="stacked-bar" aria-label="Spend distribution by provider">{data.by_provider.map((item, index) => <span key={item.name} className={`stacked-segment fill-${index}`} style={{ width: `${(item.total_cost_usd / totalProviderCost) * 100}%` }} title={`${item.name}: ${money.format(item.total_cost_usd)}`} />)}</div><div className="provider-list">{data.by_provider.map((item, index) => <Bar key={item.name} item={item} index={index} />)}</div></article><article className="panel"><div className="panel-heading"><div><p className="eyebrow">REQUEST VOLUME</p><h2>By model</h2></div><span className="panel-note">TOP 6</span></div><div className="model-list"><div className="model-row model-heading" aria-hidden="true"><span>Model</span><strong>Requests</strong><small>Cost</small></div>{data.by_model.map((item) => <div className="model-row" key={item.name}><span>{item.name}</span><strong>{item.request_count.toLocaleString()}</strong><small>{money.format(item.total_cost_usd)}</small></div>)}</div></article></section></> }
function Metric({ label, value, detail, accent = false }: { label: string; value: string; detail?: string; accent?: boolean }) { return <article className={`metric ${accent ? 'metric-accent' : ''}`}><p>{label}</p><strong>{value}</strong>{detail && <small>{detail}</small>}</article> }
function Bar({ item, index }: { item: Breakdown; index: number }) { const displayName = item.name === 'Claude' ? 'Anthropic' : item.name; return <div className="bar-item"><div className="bar-label"><span><i className={`provider-dot dot-${index}`} />{displayName}</span><strong>{money.format(item.total_cost_usd)}</strong></div><small>{item.request_count.toLocaleString()} requests</small></div> }

export default App
