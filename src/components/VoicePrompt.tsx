import React, { useState, useEffect } from 'react'
import { Mic, MicOff, Phone } from 'lucide-react'
import { supabase } from '../lib/supabase'
import toast from 'react-hot-toast'

interface VoicePromptProps {
  onAppointmentCreated: () => void
}

export function VoicePrompt({ onAppointmentCreated }: VoicePromptProps) {
  const [isRecording, setIsRecording] = useState(false)
  const [transcript, setTranscript] = useState('')
  const [currentStep, setCurrentStep] = useState<'idle' | 'name' | 'service' | 'time'>('idle')

  const recognition = 'webkitSpeechRecognition' in window
    ? new (window as any).webkitSpeechRecognition()
    : null

  useEffect(() => {
    if (recognition) {
      recognition.continuous = true
      recognition.interimResults = true
      recognition.lang = 'en-US'

      recognition.onresult = (event: any) => {
        const result = event.results[event.results.length - 1]
        if (result.isFinal) {
          setTranscript(result[0].transcript)
          handleVoiceInput(result[0].transcript)
        }
      }

      recognition.onerror = (event: any) => {
        console.error('Speech recognition error:', event.error)
        toast.error('Failed to recognize speech')
        stopRecording()
      }
    }

    return () => {
      if (recognition) {
        recognition.stop()
      }
    }
  }, [currentStep])

  const startRecording = () => {
    if (!recognition) {
      toast.error('Speech recognition is not supported in your browser')
      return
    }

    setIsRecording(true)
    setCurrentStep('name')
    recognition.start()
    speak('Please say the customer\'s name.')
  }

  const stopRecording = () => {
    if (recognition) {
      recognition.stop()
    }
    setIsRecording(false)
    setCurrentStep('idle')
    setTranscript('')
  }

  const speak = (text: string) => {
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.voice = window.speechSynthesis.getVoices().find(voice => voice.name === 'Google US English') || null
    window.speechSynthesis.speak(utterance)
  }

  const handleVoiceInput = async (input: string) => {
    switch (currentStep) {
      case 'name':
        // Create a new appointment with the customer's name
        const { data: appointment, error: appointmentError } = await supabase
          .from('appointments')
          .insert({
            customer_name: input.trim(),
            status: 'pending'
          })
          .select()
          .single()

        if (appointmentError) {
          toast.error('Failed to create appointment')
          stopRecording()
          return
        }

        setCurrentStep('service')
        speak('What service would you like to schedule?')
        break

      case 'service':
        // Update the appointment with the service type
        const { error: serviceError } = await supabase
          .from('appointments')
          .update({ service_type: input.trim() })
          .eq('customer_name', transcript)

        if (serviceError) {
          toast.error('Failed to update service type')
          stopRecording()
          return
        }

        setCurrentStep('time')
        speak('When would you like to schedule the appointment?')
        break

      case 'time':
        // Update the appointment with the time
        const { error: timeError } = await supabase
          .from('appointments')
          .update({
            appointment_time: new Date(input).toISOString(),
            status: 'scheduled'
          })
          .eq('customer_name', transcript)

        if (timeError) {
          toast.error('Failed to update appointment time')
          stopRecording()
          return
        }

        speak('Appointment created successfully')
        onAppointmentCreated()
        stopRecording()
        break
    }
  }

  return (
    <div className="fixed bottom-4 right-4">
      <button
        onClick={isRecording ? stopRecording : startRecording}
        className={`p-4 rounded-full shadow-lg ${
          isRecording ? 'bg-red-600' : 'bg-blue-600'
        } text-white hover:opacity-90 transition-opacity`}
      >
        {isRecording ? (
          <MicOff className="h-6 w-6" />
        ) : (
          <Mic className="h-6 w-6" />
        )}
      </button>

      {isRecording && (
        <div className="absolute bottom-16 right-0 bg-white rounded-lg shadow-lg p-4 w-64">
          <div className="text-sm font-medium text-gray-700 mb-2">
            {currentStep === 'name' && 'Listening for customer name...'}
            {currentStep === 'service' && 'Listening for service type...'}
            {currentStep === 'time' && 'Listening for appointment time...'}
          </div>
          <div className="text-xs text-gray-500">{transcript}</div>
        </div>
      )}
    </div>
  )
}