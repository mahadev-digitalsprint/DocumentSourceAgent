import { useEffect, useState, type FormEvent } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { alertsApi } from '../../shared/api'
import { SectionCard } from '../dashboard/SectionCard'

export function EmailAlertsPage() {
  const [smtpHost, setSmtpHost] = useState('smtp.gmail.com')
  const [smtpPort, setSmtpPort] = useState(587)
  const [smtpUser, setSmtpUser] = useState('')
  const [smtpPassword, setSmtpPassword] = useState('')
  const [emailFrom, setEmailFrom] = useState('')
  const [recipientsRaw, setRecipientsRaw] = useState('')
  const [sendOnChange, setSendOnChange] = useState(true)
  const [dailyDigestHour, setDailyDigestHour] = useState(6)
  const [message, setMessage] = useState('')
  const [errorMessage, setErrorMessage] = useState('')

  const configQuery = useQuery({
    queryKey: ['alertConfig'],
    queryFn: alertsApi.getConfig,
  })

  useEffect(() => {
    const cfg = configQuery.data
    if (!cfg) return
    setSmtpHost(cfg.smtp_host ?? 'smtp.gmail.com')
    setSmtpPort(cfg.smtp_port ?? 587)
    setSmtpUser(cfg.smtp_user ?? '')
    setEmailFrom(cfg.email_from ?? '')
    setRecipientsRaw((cfg.recipients ?? []).join('\n'))
    setSendOnChange(cfg.send_on_change ?? true)
    setDailyDigestHour(cfg.daily_digest_hour ?? 6)
  }, [configQuery.data])

  const saveMutation = useMutation({
    mutationFn: alertsApi.saveConfig,
    onSuccess: (result) => {
      setErrorMessage('')
      setMessage(result.saved ? 'Email configuration saved.' : 'Configuration save returned unexpected result.')
    },
    onError: (error: Error) => {
      setMessage('')
      setErrorMessage(error.message)
    },
  })

  const testMutation = useMutation({
    mutationFn: alertsApi.testEmail,
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
    const recipients = recipientsRaw
      .split('\n')
      .map((v) => v.trim())
      .filter(Boolean)

    saveMutation.mutate({
      smtp_host: smtpHost,
      smtp_port: smtpPort,
      smtp_user: smtpUser,
      smtp_password: smtpPassword,
      email_from: emailFrom,
      recipients,
      send_on_change: sendOnChange,
      daily_digest_hour: dailyDigestHour,
    })
  }

  return (
    <main className="mx-auto min-h-screen max-w-4xl px-4 py-6 md:px-8">
      <header className="mb-6 rounded-2xl border border-slate-700/70 bg-panel/80 p-5 shadow-panel">
        <h1 className="text-2xl font-semibold text-slate-50 md:text-3xl">Email Alerts</h1>
        <p className="mt-2 text-sm text-slate-300">Configure SMTP and recipients for change notifications and digests.</p>
      </header>

      <SectionCard title="Email Configuration" subtitle="SMTP settings and recipient policy">
        <form className="space-y-4" onSubmit={onSave}>
          <div className="grid gap-3 md:grid-cols-2">
            <div>
              <label className="mb-1 block text-sm text-slate-300">SMTP Host</label>
              <input
                value={smtpHost}
                onChange={(event) => setSmtpHost(event.target.value)}
                className="w-full rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2 text-sm text-slate-100 outline-none ring-accent focus:ring-2"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm text-slate-300">SMTP Port</label>
              <input
                type="number"
                value={smtpPort}
                onChange={(event) => setSmtpPort(Number(event.target.value))}
                className="w-full rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2 text-sm text-slate-100 outline-none ring-accent focus:ring-2"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm text-slate-300">SMTP User</label>
              <input
                value={smtpUser}
                onChange={(event) => setSmtpUser(event.target.value)}
                className="w-full rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2 text-sm text-slate-100 outline-none ring-accent focus:ring-2"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm text-slate-300">SMTP Password</label>
              <input
                type="password"
                value={smtpPassword}
                onChange={(event) => setSmtpPassword(event.target.value)}
                className="w-full rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2 text-sm text-slate-100 outline-none ring-accent focus:ring-2"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm text-slate-300">From Email</label>
              <input
                value={emailFrom}
                onChange={(event) => setEmailFrom(event.target.value)}
                className="w-full rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2 text-sm text-slate-100 outline-none ring-accent focus:ring-2"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm text-slate-300">Daily Digest Hour (UTC)</label>
              <input
                type="number"
                min={0}
                max={23}
                value={dailyDigestHour}
                onChange={(event) => setDailyDigestHour(Number(event.target.value))}
                className="w-full rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2 text-sm text-slate-100 outline-none ring-accent focus:ring-2"
              />
            </div>
          </div>

          <div>
            <label className="mb-1 block text-sm text-slate-300">Recipients (one per line)</label>
            <textarea
              value={recipientsRaw}
              onChange={(event) => setRecipientsRaw(event.target.value)}
              rows={6}
              className="w-full rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2 text-sm text-slate-100 outline-none ring-accent focus:ring-2"
            />
          </div>

          <label className="inline-flex items-center gap-2 text-sm text-slate-200">
            <input
              type="checkbox"
              checked={sendOnChange}
              onChange={(event) => setSendOnChange(event.target.checked)}
              className="h-4 w-4"
            />
            Send alert emails on detected changes
          </label>

          <div className="flex gap-2">
            <button
              type="submit"
              disabled={saveMutation.isPending}
              className="rounded-md bg-accent px-3 py-2 text-sm font-semibold text-slate-950 hover:bg-emerald-300 disabled:cursor-not-allowed disabled:bg-slate-600 disabled:text-slate-300"
            >
              {saveMutation.isPending ? 'Saving...' : 'Save Configuration'}
            </button>
            <button
              type="button"
              onClick={() => testMutation.mutate()}
              disabled={testMutation.isPending}
              className="rounded-md bg-slate-700 px-3 py-2 text-sm font-semibold text-slate-100 hover:bg-slate-600 disabled:cursor-not-allowed disabled:bg-slate-800"
            >
              {testMutation.isPending ? 'Testing...' : 'Send Test Email'}
            </button>
          </div>
        </form>

        {message ? <p className="mt-3 rounded-md border border-emerald-500/40 bg-emerald-950/30 p-2 text-sm text-emerald-200">{message}</p> : null}
        {errorMessage ? <p className="mt-3 rounded-md border border-red-500/40 bg-red-950/30 p-2 text-sm text-red-200">{errorMessage}</p> : null}
      </SectionCard>
    </main>
  )
}
