import { useEffect, useState, type FormEvent } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { alertsApi } from '../../shared/api'
import { SectionCard } from '../dashboard/SectionCard'

export function EmailAlertsPage() {
  const [receiverEmail, setReceiverEmail] = useState('')
  const [message, setMessage] = useState('')
  const [errorMessage, setErrorMessage] = useState('')

  const configQuery = useQuery({
    queryKey: ['alertSimpleConfig'],
    queryFn: alertsApi.getSimpleConfig,
  })

  useEffect(() => {
    const cfg = configQuery.data
    if (!cfg) return
    setReceiverEmail(cfg.receiver_email ?? '')
  }, [configQuery.data])

  const saveMutation = useMutation({
    mutationFn: (email: string) => alertsApi.saveSimpleConfig(email),
    onSuccess: (result) => {
      setErrorMessage('')
      setMessage(result.saved ? 'Receiver email saved.' : 'Save completed with unexpected response.')
    },
    onError: (error: Error) => {
      setMessage('')
      setErrorMessage(error.message)
    },
  })

  const testMutation = useMutation({
    mutationFn: (email: string) => alertsApi.testEmail(email),
    onSuccess: (result) => {
      if (result.sent) {
        setErrorMessage('')
        setMessage('Test email sent successfully.')
      } else {
        setMessage('')
        setErrorMessage(result.error ?? 'Test email failed.')
      }
    },
    onError: (error: Error) => {
      setMessage('')
      setErrorMessage(error.message)
    },
  })

  const onSave = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    saveMutation.mutate(receiverEmail)
  }

  return (
    <main className="mx-auto min-h-screen max-w-4xl px-4 py-6 md:px-8">
      <header className="mb-6 rounded-2xl border border-slate-700/70 bg-panel/80 p-5 shadow-panel">
        <h1 className="text-2xl font-semibold text-slate-50 md:text-3xl">Email Alerts</h1>
        <p className="mt-2 text-sm text-slate-300">Only receiver email is required. SMTP sender is handled by backend configuration.</p>
      </header>

      <SectionCard title="Receiver Setup" subtitle="Set one receiver email for all alert and digest notifications">
        <form className="space-y-4" onSubmit={onSave}>
          <div>
            <label className="mb-1 block text-sm text-slate-300">Receiver Email</label>
            <input
              type="email"
              value={receiverEmail}
              onChange={(event) => setReceiverEmail(event.target.value)}
              placeholder="receiver@company.com"
              className="w-full rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2 text-sm text-slate-100 outline-none ring-accent focus:ring-2"
            />
          </div>

          <div className="flex gap-2">
            <button
              type="submit"
              disabled={saveMutation.isPending}
              className="rounded-md bg-accent px-3 py-2 text-sm font-semibold text-slate-950 hover:bg-emerald-300 disabled:cursor-not-allowed disabled:bg-slate-600 disabled:text-slate-300"
            >
              {saveMutation.isPending ? 'Saving...' : 'Save Receiver'}
            </button>
            <button
              type="button"
              onClick={() => testMutation.mutate(receiverEmail)}
              disabled={testMutation.isPending}
              className="rounded-md bg-slate-700 px-3 py-2 text-sm font-semibold text-slate-100 hover:bg-slate-600 disabled:cursor-not-allowed disabled:bg-slate-800"
            >
              {testMutation.isPending ? 'Testing...' : 'Send Test Email'}
            </button>
          </div>
        </form>

        {configQuery.data ? (
          <div className="mt-4 rounded-lg border border-slate-700/70 bg-slate-900/40 p-3 text-xs text-slate-400">
            <p>Sender: {configQuery.data.sender_email}</p>
            <p>Configured: {configQuery.data.configured ? 'Yes' : 'No'}</p>
          </div>
        ) : null}

        {message ? <p className="mt-3 rounded-md border border-emerald-500/40 bg-emerald-950/30 p-2 text-sm text-emerald-200">{message}</p> : null}
        {errorMessage ? <p className="mt-3 rounded-md border border-red-500/40 bg-red-950/30 p-2 text-sm text-red-200">{errorMessage}</p> : null}
      </SectionCard>
    </main>
  )
}
