// ------------------------------------------------------------------
// Forecast.jsx (Oct 12-13) - owner-only. Shows next month's predicted demand for each
// product. Click a row to see the past months as a chart and how the three methods compared.
// ------------------------------------------------------------------
import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { MonthlyChart } from '../components/Charts.jsx'
import { Alert, Card, PageHeader, Spinner } from '../components/ui.jsx'

export default function Forecast() {
  const [list, setList] = useState(null)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState(null) // product_id
  const [detail, setDetail] = useState(null)
  const [detailError, setDetailError] = useState('')
  const [detailLoading, setDetailLoading] = useState(false)

  useEffect(() => {
    let cancelled = false
    api('/forecast')
      .then((d) => !cancelled && setList(d))
      .catch((err) => !cancelled && setError(err.message))
    return () => {
      cancelled = true
    }
  }, [])

  async function openProduct(id) {
    setSelected(id)
    setDetail(null)
    setDetailError('')
    setDetailLoading(true)
    try {
      setDetail(await api(`/forecast/${id}`))
    } catch (err) {
      setDetailError(err.message)
    } finally {
      setDetailLoading(false)
    }
  }

  if (error) return <Alert type="error">{error}</Alert>
  if (!list) return <Spinner label="Calculating forecasts..." />

  return (
    <div className="space-y-6">
      <PageHeader
        title="Demand forecast"
        subtitle="Predicted units sold next month, learned from past sales and the crop season."
      />

      <div className="grid gap-6 xl:grid-cols-5">
        <div className="xl:col-span-3">
        <Card title="All products">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
                <tr>
                  <th className="py-2 pr-3">Product</th>
                  <th className="px-3">Season</th>
                  <th className="px-3">Month</th>
                  <th className="px-3 text-right">Predicted</th>
                  <th className="pl-3">Method</th>
                </tr>
              </thead>
              <tbody>
                {list.map((f) => (
                  <tr
                    key={f.product_id}
                    onClick={() => openProduct(f.product_id)}
                    className={`cursor-pointer border-b border-slate-100 hover:bg-slate-50 ${
                      selected === f.product_id ? 'bg-brand-50' : ''
                    }`}
                  >
                    <td className="py-2.5 pr-3 font-medium text-slate-800">{f.product_name}</td>
                    <td className="px-3 text-slate-600">{f.season}</td>
                    {f.enough_data ? (
                      <>
                        <td className="px-3">{f.forecast_month}</td>
                        <td className="px-3 text-right font-semibold">{f.predicted_demand}</td>
                        <td className="pl-3 text-slate-600">{f.best_method_label}</td>
                      </>
                    ) : (
                      <td colSpan={3} className="px-3 text-xs text-slate-500">
                        Not enough sales history yet
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
        </div>

        <div className="xl:col-span-2">
        <Card title={detail ? detail.product_name : 'Details'}>
          {!selected && <p className="text-sm text-slate-500">Click a product to see its sales history and how the forecast was made.</p>}
          {detailLoading && <Spinner label="Loading..." />}
          {detailError && <Alert type="error">{detailError}</Alert>}
          {detail && (
            <div className="space-y-4">
              <MonthlyChart
                history={detail.history}
                forecastMonth={detail.enough_data ? detail.forecast_month : null}
                predicted={detail.enough_data ? detail.predicted_demand : null}
              />
              <p className="text-xs text-slate-500">Green = units sold in past months. Amber = predicted for next month.</p>

              {!detail.enough_data ? (
                <Alert type="warning">{detail.message}</Alert>
              ) : (
                <>
                  <Alert type="info" title={`Prediction: ${detail.predicted_demand} units in ${detail.forecast_month}`}>
                    {detail.explanation}
                  </Alert>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm">
                      <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
                        <tr>
                          <th className="py-2 pr-3">Method</th>
                          <th className="px-3 text-right">Test error (MAE)</th>
                          <th className="pl-3 text-right">Prediction</th>
                        </tr>
                      </thead>
                      <tbody>
                        {detail.methods.map((m) => (
                          <tr key={m.method} className={`border-b border-slate-100 ${m.method === detail.best_method ? 'bg-brand-50 font-semibold' : ''}`}>
                            <td className="py-2 pr-3">
                              {m.label} {m.method === detail.best_method && <span className="text-xs text-brand-700">(used)</span>}
                            </td>
                            <td className="px-3 text-right">{m.mae}</td>
                            <td className="pl-3 text-right">{m.prediction}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <p className="text-xs text-slate-500">
                    MAE = the average mistake (in units) when each method was tested on the last {detail.backtest_months} months.
                    Smaller is better.
                  </p>
                </>
              )}
            </div>
          )}
        </Card>
        </div>
      </div>
    </div>
  )
}
