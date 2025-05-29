import { createClient } from 'npm:@supabase/supabase-js@2.39.7'
import { format, addDays, setHours } from 'npm:date-fns@3.3.1'
import twilio from 'npm:twilio@4.22.0'
const VoiceResponse = twilio.twiml.VoiceResponse

interface Service {
  id: string
  name: string
  description: string
  duration: number
  price: number
  is_emergency: boolean
  category: string
}

interface CallState {
  call_sid: string
  current_step: string
  language: string
  metadata: {
    categories?: string[]
    services?: Service[]
    selected_category?: string
    selected_service?: Service
    time_slots?: string[]
    customer_name?: string
    notes?: string
  }
}

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Content-Type': 'application/xml; charset=utf-8'
}

const BUSINESS_HOURS = {
  start: 8, // 8 AM
  end: 18   // 6 PM
}

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { 
      status: 204, 
      headers: corsHeaders 
    })
  }

  const twiml = new VoiceResponse()

  try {
    const supabase = createClient(
      Deno.env.get('SUPABASE_URL') ?? '',
      Deno.env.get('SUPABASE_ANON_KEY') ?? '',
      {
        auth: {
          persistSession: false,
          autoRefreshToken: false
        }
      }
    )

    const formData = await req.formData()
    const digits = formData.get('Digits')?.toString()
    const callSid = formData.get('CallSid')?.toString()
    const phoneNumber = formData.get('From')?.toString()
    const step = new URL(req.url).searchParams.get('step') || 'welcome'

    if (!callSid) {
      throw new Error('Missing CallSid')
    }

    // Get call state
    const { data: callStates } = await supabase
      .from('call_states')
      .select('current_step, language, metadata')
      .eq('call_sid', callSid)

    // Get the first call state or use defaults
    const callState = callStates?.[0] || {
      current_step: 'welcome',
      language: 'en',
      metadata: {}
    }

    const language = callState.language || 'en'
    const voice = language === 'es' ? 'Polly.Lupe' : 'Polly.Matthew'
    const metadata = callState.metadata || {}

    // Log IVR interaction
    await supabase.from('ivr_logs').insert({
      call_sid: callSid,
      step,
      input: digits || null
    })

    switch (step) {
      case 'welcome':
        twiml.say(
          { voice: 'Polly.Matthew' },
          'Welcome to L B Automotive. For English, press 1. Para español, presione 2.'
        )
        twiml.gather({
          numDigits: 1,
          timeout: 10,
          action: '/functions/v1/twilio-webhook?step=language',
          method: 'POST'
        })
        break

      case 'language':
        await supabase
          .from('call_states')
          .upsert({
            call_sid: callSid,
            current_step: 'menu',
            language: digits === '2' ? 'es' : 'en'
          })

        twiml.redirect('/functions/v1/twilio-webhook?step=menu')
        break

      case 'menu':
        twiml.say(
          { voice },
          language === 'es'
            ? 'Para programar una cita, presione 1. Para emergencias, presione 2.'
            : 'To schedule an appointment, press 1. For emergencies, press 2.'
        )
        twiml.gather({
          numDigits: 1,
          timeout: 10,
          action: '/functions/v1/twilio-webhook?step=route',
          method: 'POST'
        })
        break

      case 'route':
        if (digits === '1') {
          // Get service categories
          const { data: categories } = await supabase
            .from('services')
            .select('category')
            .distinct()

          // Update metadata with categories
          await supabase
            .from('call_states')
            .update({
              current_step: 'select_category',
              metadata: {
                ...metadata,
                categories: categories?.map(c => c.category) || []
              }
            })
            .eq('call_sid', callSid)

          twiml.say(
            { voice },
            language === 'es'
              ? 'Por favor seleccione una categoría de servicio:'
              : 'Please select a service category:'
          )

          categories?.forEach((cat, index) => {
            twiml.say(
              { voice },
              language === 'es'
                ? `Para ${cat.category}, presione ${index + 1}`
                : `For ${cat.category}, press ${index + 1}`
            )
          })

          twiml.gather({
            numDigits: 1,
            timeout: 10,
            action: '/functions/v1/twilio-webhook?step=select_service',
            method: 'POST'
          })
        } else if (digits === '2') {
          // Handle emergency services
          const { data: emergencyServices } = await supabase
            .from('services')
            .select('*')
            .eq('is_emergency', true)
            .order('name')

          await supabase
            .from('call_states')
            .update({
              current_step: 'select_emergency',
              metadata: {
                ...metadata,
                services: emergencyServices
              }
            })
            .eq('call_sid', callSid)

          twiml.say(
            { voice },
            language === 'es'
              ? 'Por favor seleccione el servicio de emergencia que necesita:'
              : 'Please select the emergency service you need:'
          )

          emergencyServices?.forEach((service, index) => {
            twiml.say(
              { voice },
              language === 'es'
                ? `Para ${service.name}, presione ${index + 1}`
                : `For ${service.name}, press ${index + 1}`
            )
          })

          twiml.gather({
            numDigits: 1,
            timeout: 10,
            action: '/functions/v1/twilio-webhook?step=confirm_emergency',
            method: 'POST'
          })
        }
        break

      case 'select_service':
        if (!digits) {
          twiml.say(
            { voice },
            language === 'es'
              ? 'Por favor seleccione una categoría de servicio'
              : 'Please select a service category'
          )
          twiml.redirect('/functions/v1/twilio-webhook?step=select_service')
          break
        }

        const categoryIndex = parseInt(digits) - 1
        const selectedCategory = metadata.categories[categoryIndex]

        if (!selectedCategory) {
          twiml.say(
            { voice },
            language === 'es'
              ? 'Categoría no válida. Por favor, intente de nuevo'
              : 'Invalid category. Please try again'
          )
          twiml.redirect('/functions/v1/twilio-webhook?step=select_service')
          break
        }

        // Get services for selected category
        const { data: services } = await supabase
          .from('services')
          .select('*')
          .eq('category', selectedCategory)
          .order('name')

        if (!services || services.length === 0) {
          twiml.say(
            { voice },
            language === 'es'
              ? 'No hay servicios disponibles en esta categoría. Por favor, intente otra categoría.'
              : 'No services available in this category. Please try another category.'
          )
          twiml.redirect('/functions/v1/twilio-webhook?step=select_category')
          break
        }

        await supabase
          .from('call_states')
          .update({
            current_step: 'select_service_detail',
            metadata: {
              ...metadata,
              services,
              selected_category: selectedCategory
            }
          })
          .eq('call_sid', callSid)

        twiml.say(
          { voice },
          language === 'es'
            ? `Por favor seleccione el servicio que necesita para ${selectedCategory}`
            : `Please select the service you need for ${selectedCategory}`
        )

        services?.forEach((service, index) => {
          twiml.say(
            { voice },
            language === 'es'
              ? `Para ${service.name} (${service.duration} minutos, $${service.price}), presione ${index + 1}`
              : `For ${service.name} (${service.duration} minutes, $${service.price}), press ${index + 1}`
          )
        })

        twiml.gather({
          numDigits: 1,
          timeout: 10,
          action: '/functions/v1/twilio-webhook?step=select_time',
          method: 'POST'
        })
        break

      case 'select_time':
        if (!digits) {
          twiml.say(
            { voice },
            language === 'es'
              ? 'Por favor seleccione un servicio'
              : 'Please select a service'
          )
          twiml.redirect('/functions/v1/twilio-webhook?step=select_time')
          break
        }

        const serviceIndex = parseInt(digits) - 1
        const selectedService = metadata.services?.[serviceIndex]

        if (!selectedService) {
          twiml.say(
            { voice },
            language === 'es'
              ? 'Servicio no válido. Por favor, intente de nuevo'
              : 'Invalid service. Please try again'
          )
          twiml.redirect('/functions/v1/twilio-webhook?step=select_time')
          break
        }

        // Get available time slots
        const today = new Date()
        const tomorrow = addDays(today, 1)
        const timeSlots = []

        for (let hour = BUSINESS_HOURS.start; hour < BUSINESS_HOURS.end; hour++) {
          const time = format(new Date(tomorrow.setHours(hour, 0, 0)), 'HH:mm')
          timeSlots.push(time)
        }

        await supabase
          .from('call_states')
          .update({
            current_step: 'select_time_slot',
            metadata: {
              ...metadata,
              selected_service: selectedService,
              time_slots: timeSlots
            }
          })
          .eq('call_sid', callSid)

        twiml.say(
          { voice },
          language === 'es'
            ? 'Por favor seleccione la hora que prefiera para su cita'
            : 'Please select your preferred time for the appointment'
        )

        timeSlots.forEach((time, index) => {
          twiml.say(
            { voice },
            language === 'es'
              ? `Para ${time}, presione ${index + 1}`
              : `For ${time}, press ${index + 1}`
          )
        })

        twiml.gather({
          numDigits: 1,
          timeout: 10,
          action: '/functions/v1/twilio-webhook?step=confirm_booking',
          method: 'POST'
        })
        break

      case 'confirm_booking':
        if (!digits) {
          twiml.say(
            { voice },
            language === 'es'
              ? 'Por favor seleccione una hora'
              : 'Please select a time'
          )
          twiml.redirect('/functions/v1/twilio-webhook?step=confirm_booking')
          break
        }

        const timeSlotIndex = parseInt(digits) - 1
        const selectedTime = metadata.time_slots?.[timeSlotIndex]

        if (!selectedTime) {
          twiml.say(
            { voice },
            language === 'es'
              ? 'Hora no válida. Por favor, intente de nuevo'
              : 'Invalid time. Please try again'
          )
          twiml.redirect('/functions/v1/twilio-webhook?step=confirm_booking')
          break
        }

        // Create appointment
        const [hours, minutes] = selectedTime.split(':').map(Number)
        const tomorrow = addDays(new Date(), 1)
        const appointmentDate = format(
          setHours(tomorrow, hours, minutes),
          'yyyy-MM-ddTHH:mm:ss.SSSxxx'
        )

        const { data: appointment } = await supabase
          .from('appointments')
          .insert([
            {
              customer_name: metadata.customer_name,
              phone_number: phoneNumber,
              appointment_time: appointmentDate,
              service_type: metadata.selected_service.name,
              notes: metadata.notes,
              status: 'pending',
              emergency_request: false
            }
          ])
          .select()
          .single()

        twiml.say(
          { voice },
          language === 'es'
            ? `Gracias por programar su cita. Su cita para ${metadata.selected_service.name} está programada para mañana a las ${selectedTime}. ¿Necesita algo más?`
            : `Thank you for scheduling your appointment. Your appointment for ${metadata.selected_service.name} is scheduled for tomorrow at ${selectedTime}. Is there anything else you need?`
        )

        // Hang up after confirmation
        twiml.hangup()
        break
        if (!digits) {
          twiml.say(
            { voice },
            language === 'es'
              ? 'No se detectó ninguna selección. Por favor, intente de nuevo.'
              : 'No selection detected. Please try again.'
          )
          break
        }

        const selectedCategory = metadata.categories?.[Number(digits) - 1]
        if (selectedCategory) {
          const { data: services } = await supabase
            .from('services')
            .select('*')
            .eq('category', selectedCategory)
            .order('name')

          await supabase
            .from('call_states')
            .update({
              metadata: {
                ...metadata,
                selectedCategory,
                services
              }
            })
            .eq('call_sid', callSid)

          twiml.say(
            { voice },
            language === 'es'
              ? 'Por favor seleccione el servicio específico:'
              : 'Please select the specific service:'
          )

          services?.forEach((service, index) => {
            twiml.say(
              { voice },
              language === 'es'
                ? `Para ${service.name}, ${service.duration} minutos, $${service.price}, presione ${index + 1}`
                : `For ${service.name}, ${service.duration} minutes, $${service.price}, press ${index + 1}`
            )
          })

          twiml.gather({
            numDigits: 1,
            timeout: 10,
            action: '/functions/v1/twilio-webhook?step=get_name',
            method: 'POST'
          })
        }
        break

      case 'get_name':
        if (!digits) {
          twiml.say(
            { voice },
            language === 'es'
              ? 'No se detectó ninguna selección. Por favor, intente de nuevo.'
              : 'No selection detected. Please try again.'
          )
          break
        }

        const selectedService = metadata.services?.[Number(digits) - 1]
        if (selectedService) {
          await supabase
            .from('call_states')
            .update({
              metadata: {
                ...metadata,
                selectedService
              }
            })
            .eq('call_sid', callSid)

          twiml.say(
            { voice },
            language === 'es'
              ? 'Por favor diga su nombre después del tono.'
              : 'Please say your name after the tone.'
          )

          twiml.record({
            action: '/functions/v1/twilio-webhook?step=select_time',
            method: 'POST',
            maxLength: 10,
            playBeep: true
          })
        }
        break

      case 'select_time':
        // Get available slots for next 5 business days
        const startDate = addDays(new Date(), 1) // Start from tomorrow
        const { data: slots } = await supabase
          .from('available_slots')
          .select('*')
          .gte('start_time', startDate.toISOString())
          .eq('is_available', true)
          .order('start_time')
          .limit(5)

        await supabase
          .from('call_states')
          .update({
            metadata: {
              ...metadata,
              slots
            }
          })
          .eq('call_sid', callSid)

        twiml.say(
          { voice },
          language === 'es'
            ? 'Por favor seleccione un horario disponible:'
            : 'Please select an available time slot:'
        )

        slots?.forEach((slot, index) => {
          const formattedTime = format(new Date(slot.start_time), 'EEEE, MMMM d, h:mm a')
          twiml.say(
            { voice },
            language === 'es'
              ? `Para ${formattedTime}, presione ${index + 1}`
              : `For ${formattedTime}, press ${index + 1}`
          )
        })

        twiml.gather({
          numDigits: 1,
          timeout: 10,
          action: '/functions/v1/twilio-webhook?step=confirm_booking',
          method: 'POST'
        })
        break

      case 'confirm_booking':
        if (!digits) {
          twiml.say(
            { voice },
            language === 'es'
              ? 'No se detectó ninguna selección. Por favor, intente de nuevo.'
              : 'No selection detected. Please try again.'
          )
          break
        }

        const selectedSlot = metadata.slots?.[Number(digits) - 1]
        const selectedServiceDetails = metadata.selectedService

        if (selectedSlot && selectedServiceDetails) {
          // Create appointment
          const { data: appointment, error: appointmentError } = await supabase
            .from('appointments')
            .insert({
              customer_name: 'Customer', // Will be updated with transcribed name
              phone_number: phoneNumber,
              appointment_time: selectedSlot.start_time,
              service_type: selectedServiceDetails.name,
              status: 'scheduled',
              emergency_request: selectedServiceDetails.is_emergency || false
            })
            .select()
            .single()

          if (appointmentError) throw appointmentError

          // Mark slot as unavailable
          await supabase
            .from('available_slots')
            .update({ is_available: false })
            .eq('id', selectedSlot.id)

          // Update call state with appointment
          await supabase
            .from('call_states')
            .update({
              appointment_id: appointment.id,
              metadata: {
                ...metadata,
                selectedSlot,
                appointment
              }
            })
            .eq('call_sid', callSid)

          const formattedTime = format(new Date(selectedSlot.start_time), 'EEEE, MMMM d, h:mm a')
          twiml.say(
            { voice },
            language === 'es'
              ? `Su cita ha sido programada para ${formattedTime}. Le enviaremos un mensaje de confirmación. Gracias por llamar.`
              : `Your appointment has been scheduled for ${formattedTime}. We will send you a confirmation message. Thank you for calling.`
          )
          twiml.hangup()
        }
        break

      default:
        twiml.say(
          { voice },
          language === 'es'
            ? 'Gracias por llamar a L B Automotive. Adiós.'
            : 'Thank you for calling L B Automotive. Goodbye.'
        )
        twiml.hangup()
    }

    // Update last response time
    await supabase
      .from('call_states')
      .update({
        last_response_time: 'NOW()',
        updated_at: 'NOW()'
      })
      .eq('call_sid', callSid)

    return new Response(twiml.toString(), { headers: corsHeaders })

  } catch (error) {
    console.error('Error in webhook:', error)

    twiml.say(
      { voice: 'Polly.Matthew' },
      'We are experiencing technical difficulties. Please try again later.'
    )
    twiml.hangup()

    return new Response(twiml.toString(), { headers: corsHeaders })
  }
})