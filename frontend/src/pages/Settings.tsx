import React, { useId, useState, useEffect } from 'react'
import { useSelector } from 'react-redux'
import { Link } from 'react-router-dom'
import { User as UserIcon, Shield, UserCog } from 'lucide-react'
import { RootState } from '../store/store'

const DISPLAY_TIMEZONE_KEY = 'lb_display_timezone'

const DISPLAY_TIMEZONES = [
  { value: '', label: 'Use business default' },
  { value: 'America/New_York', label: 'Eastern (America/New_York)' },
  { value: 'America/Chicago', label: 'Central (America/Chicago)' },
  { value: 'America/Denver', label: 'Mountain (America/Denver)' },
  { value: 'America/Los_Angeles', label: 'Pacific (America/Los_Angeles)' },
  { value: 'UTC', label: 'UTC' },
  { value: 'Europe/London', label: 'Europe/London' },
  { value: 'Asia/Tokyo', label: 'Asia/Tokyo' },
]

export function Settings() {
  const formId = useId()
  const user = useSelector((state: RootState) => state.auth.user)
  const [displayTimezone, setDisplayTimezone] = useState('')
  useEffect(() => {
    setDisplayTimezone(globalThis.localStorage?.getItem(DISPLAY_TIMEZONE_KEY) ?? '')
  }, [])

  const handleDisplayTimezoneChange = (value: string) => {
    if (value) {
      globalThis.localStorage?.setItem(DISPLAY_TIMEZONE_KEY, value)
    } else {
      globalThis.localStorage?.removeItem(DISPLAY_TIMEZONE_KEY)
    }
    setDisplayTimezone(value)
  }

  const roleLabel = (() => {
    if (user?.is_admin) return 'Administrator'
    if (user?.staff_id) return 'Staff'
    return 'User'
  })()

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">Settings</h1>
      </div>

      <div className="bg-white dark:bg-gray-800 shadow rounded-lg">
        <div className="p-6 space-y-6">
          <div className="border-b border-gray-200 dark:border-gray-700 pb-6">
            <h2 className="text-lg font-medium text-gray-900 dark:text-white flex items-center gap-2">
              <UserIcon className="h-5 w-5 text-gray-500" />
              Account
            </h2>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Your account details and display preferences.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-6">
            <div>
              <label htmlFor={`${formId}-username`} className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                Username
              </label>
              <div
                id={`${formId}-username`}
                className="mt-1 block w-full rounded-md border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-gray-900 dark:text-white sm:text-sm"
              >
                {user?.username || '—'}
              </div>
            </div>

            <div>
              <label htmlFor={`${formId}-role`} className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                Role
              </label>
              <div
                id={`${formId}-role`}
                className="mt-1 flex items-center gap-2 w-full rounded-md border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-gray-900 dark:text-white sm:text-sm"
              >
                {user?.is_admin ? (
                  <Shield className="h-4 w-4 text-amber-500" aria-hidden />
                ) : (
                  <UserCog className="h-4 w-4 text-gray-500" aria-hidden />
                )}
                {roleLabel}
              </div>
            </div>

            <div>
              <label htmlFor={`${formId}-display-tz`} className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                Display timezone
              </label>
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">
                Override how dates and times are shown for you. Does not change business scheduling.
              </p>
              <select
                id={`${formId}-display-tz`}
                value={displayTimezone}
                onChange={(e) => handleDisplayTimezoneChange(e.target.value)}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-lb-red-primary focus:ring-lb-red-primary dark:bg-gray-700 dark:border-gray-600 dark:text-white sm:text-sm"
              >
                {DISPLAY_TIMEZONES.map(({ value, label }) => (
                  <option key={`tz-${value || 'default'}`} value={value}>{label}</option>
                ))}
              </select>
            </div>
          </div>
        </div>
      </div>

      {user?.is_admin && (
        <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg p-4">
          <p className="text-sm text-amber-800 dark:text-amber-200">
            Business-wide settings (timezone, staff count, contact) are in{' '}
            <Link to="/admin/settings" className="font-medium underline hover:no-underline">
              Admin → Admin Settings
            </Link>
            .
          </p>
        </div>
      )}

      {!user?.is_admin && (
        <div className="bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Business and system settings are managed by your administrator.
          </p>
        </div>
      )}
    </div>
  )
}

export default Settings
