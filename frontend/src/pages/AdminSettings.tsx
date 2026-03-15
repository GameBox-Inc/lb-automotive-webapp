import React, { useId, useState, useEffect } from 'react'
import { apiClient } from '../lib/supabase'
import { Setting } from '../types'
import toast from 'react-hot-toast'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { Sliders } from 'lucide-react'

const TIMEZONES = [
  'UTC',
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'Europe/London',
  'Europe/Paris',
  'Asia/Tokyo',
  'Australia/Sydney',
]

export function AdminSettings() {
  const formId = useId()
  const [settings, setSettings] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    fetchSettings()
  }, [])

  const fetchSettings = async () => {
    try {
      const data = await apiClient.getSettings()
      const settingsMap = data.reduce((acc: Record<string, string>, curr: Setting) => {
        acc[curr.key] = curr.value
        return acc
      }, {})
      setSettings(settingsMap)
    } catch (error) {
      console.error('Error fetching settings:', error)
      toast.error('Failed to load settings')
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async (key: string, value: string) => {
    setSaving(true)
    try {
      await apiClient.updateSetting(key, value)
      setSettings(prev => ({ ...prev, [key]: value }))
      toast.success('Setting updated')
    } catch (error) {
      console.error('Error updating setting:', error)
      toast.error('Failed to update setting')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <LoadingSpinner />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">Admin Settings</h1>
      </div>

      <div className="bg-white dark:bg-gray-800 shadow rounded-lg">
        <div className="p-6 space-y-6">
          <div className="border-b border-gray-200 dark:border-gray-700 pb-6">
            <h2 className="text-lg font-medium text-gray-900 dark:text-white flex items-center gap-2">
              <Sliders className="h-5 w-5 text-gray-500" />
              Business & system
            </h2>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Configure business-wide settings. These affect scheduling, IVR, and system behavior.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-6">
            <div>
              <label htmlFor={`${formId}-timezone`} className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                Business timezone
              </label>
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">
                All appointments and schedules use this timezone.
              </p>
              <select
                id={`${formId}-timezone`}
                value={settings['timezone'] || 'America/New_York'}
                onChange={(e) => handleSave('timezone', e.target.value)}
                disabled={saving}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-lb-red-primary focus:ring-lb-red-primary dark:bg-gray-700 dark:border-gray-600 dark:text-white sm:text-sm"
              >
                {TIMEZONES.map(tz => (
                  <option key={tz} value={tz}>{tz}</option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor={`${formId}-staff-count`} className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                Daily staff count
              </label>
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">
                Maximum number of active staff visible on the schedule.
              </p>
              <input
                id={`${formId}-staff-count`}
                type="number"
                value={settings['staff_count'] || '5'}
                onChange={(e) => handleSave('staff_count', e.target.value)}
                disabled={saving}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-lb-red-primary focus:ring-lb-red-primary dark:bg-gray-700 dark:border-gray-600 dark:text-white sm:text-sm"
              />
            </div>

            <div>
              <label htmlFor={`${formId}-email`} className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                Business email
              </label>
              <input
                id={`${formId}-email`}
                type="email"
                defaultValue="contact@lbautomotive.com"
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-lb-red-primary focus:ring-lb-red-primary dark:bg-gray-700 dark:border-gray-600 dark:text-white sm:text-sm"
                disabled
              />
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">Contact system administrator to change.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default AdminSettings
