import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

if (!supabaseUrl || !supabaseAnonKey) {
  throw new Error('Missing Supabase environment variables')
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: true
  }
})

export const updateAppointmentStatus = async (id: string, status: string) => {
  const { error } = await supabase
    .from('appointments')
    .update({ status })
    .eq('id', id)

  if (error) throw error
}

export const rescheduleAppointment = async (id: string, appointmentTime: string) => {
  const { error } = await supabase
    .from('appointments')
    .update({ 
      appointment_time: appointmentTime,
      status: 'rescheduled'
    })
    .eq('id', id)

  if (error) throw error
}

export const logError = async (error: any, context: string, metadata?: any) => {
  const { error: logError } = await supabase
    .from('error_logs')
    .insert([{
      error_message: error.message,
      error_stack: error.stack,
      context,
      metadata,
      created_at: new Date().toISOString()
    }])

  if (logError) {
    console.error('Failed to log error:', logError)
  }
}

// Subscribe to real-time changes
export const subscribeToAppointments = (callback: (payload: any) => void) => {
  return supabase
    .channel('appointments')
    .on(
      'postgres_changes',
      { event: '*', schema: 'public', table: 'appointments' },
      callback
    )
    .subscribe()
}

export const getAppointmentsByTimeframe = async (timeframe: '24h' | '7d' | '30d') => {
  const now = new Date()
  const start = new Date()

  switch (timeframe) {
    case '24h':
      start.setHours(start.getHours() - 24)
      break
    case '7d':
      start.setDate(start.getDate() - 7)
      break
    case '30d':
      start.setDate(start.getDate() - 30)
      break
  }

  const { data, error } = await supabase
    .from('appointments')
    .select('*')
    .gte('appointment_time', start.toISOString())
    .lte('appointment_time', now.toISOString())
    .order('appointment_time', { ascending: false })

  if (error) throw error
  return data
}