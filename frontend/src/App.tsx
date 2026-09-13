import { useEffect, useState } from 'react'
import './App.css'

const API_URL = 'https://llm-analytics-api-zghvsfuxiq-ew.a.run.app'
type Breakdown = { name: string; request_count: number; total_cost_usd: number }
type Analytics = { summary: { request_count: number; total_cost_usd: number; input_tokens: number; output_tokens: number; average_latency_ms: number; successful_requests: number; failed_requests: number }; by_provider: Breakdown[]; by_model: Breakdown[] }
const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 })
const compact = new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 })

function App() {
  const [data, setData] = useState<Analytics | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    fetch(API_URL).then((response) => {
      if (!response.ok) throw new Error('The analytics API is unavailable.')
      return response.json() as Promise<Analytics>
    }).then(setData).catch((requestError: Error) => setError(requestError.message))
  }, [])

  return (
    <main className="shell"><header className="topbar"><a className="brand" href="#top"><span className="brand-mark">λ</span><span>LLM Cost <strong>Analytics</strong></span></a><div className="live-status"><span /> LIVE DATA <small>GCP / BigQuery</small></div></header>
      <section className="hero" id="top"><div><p className="eyebrow">OPERATIONS CONSOLE / 01</p><h1>Know what your<br /><em>models cost.</em></h1><p className="hero-copy">A clear view of LLM activity, latency, and spend across your production-like workload.</p></div><div className="hero-orbit" aria-hidden="true"><div className="orbit-ring" /><div className="orbit-core">$</div></div></section>
      {error && <div className="error-banner">Could not connect to analytics API: {error}</div>}
      {!data && !error && <div className="loading">Loading warehouse telemetry<span>...</span></div>}
      {data && <Dashboard data={data} />}
      <footer><span>LLM COST ANALYTICS PIPELINE</span><span>Cloud Storage → Functions → BigQuery → React</span></footer></main>
  )
}

function Dashboard({ data }: { data: Analytics }) { const { summary } = data; const successRate = summary.request_count ? (summary.successful_requests / summary.request_count) * 100 : 0; const maxProviderCost = Math.max(...data.by_provider.map((item) => item.total_cost_usd)); return <><section className="kpi-grid" aria-label="Key metrics"><Metric label="Total spend" value={money.format(summary.total_cost_usd)} accent /><Metric label="Requests processed" value={compact.format(summary.request_count)} detail={`${summary.successful_requests.toLocaleString()} successful`} /><Metric label="Average latency" value={`${Math.round(summary.average_latency_ms)} ms`} detail={`${successRate.toFixed(1)}% success rate`} /><Metric label="Tokens consumed" value={compact.format(summary.input_tokens + summary.output_tokens)} detail={`${compact.format(summary.input_tokens)} in / ${compact.format(summary.output_tokens)} out`} /></section><section className="analysis-grid"><article className="panel"><div className="panel-heading"><div><p className="eyebrow">SPEND DISTRIBUTION</p><h2>By provider</h2></div><span className="panel-note">USD</span></div><div className="bar-list">{data.by_provider.map((item, index) => <Bar key={item.name} item={item} max={maxProviderCost} index={index} />)}</div></article><article className="panel"><div className="panel-heading"><div><p className="eyebrow">REQUEST VOLUME</p><h2>By model</h2></div><span className="panel-note">TOP 6</span></div><div className="model-list">{data.by_model.map((item) => <div className="model-row" key={item.name}><span>{item.name}</span><strong>{item.request_count.toLocaleString()}</strong><small>{money.format(item.total_cost_usd)}</small></div>)}</div></article></section></> }
function Metric({ label, value, detail, accent = false }: { label: string; value: string; detail?: string; accent?: boolean }) { return <article className={`metric ${accent ? 'metric-accent' : ''}`}><p>{label}</p><strong>{value}</strong>{detail && <small>{detail}</small>}</article> }
function Bar({ item, max, index }: { item: Breakdown; max: number; index: number }) { return <div className="bar-item"><div className="bar-label"><span><i className={`provider-dot dot-${index}`} />{item.name}</span><strong>{money.format(item.total_cost_usd)}</strong></div><div className="bar-track"><div className={`bar-fill fill-${index}`} style={{ width: `${(item.total_cost_usd / max) * 100}%` }} /></div><small>{item.request_count.toLocaleString()} requests</small></div> }

export default App
