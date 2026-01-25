import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Wrench, User, Lock, ArrowRight, Check, Loader2 } from 'lucide-react'
import { apiClient } from '../lib/supabase'
import toast from 'react-hot-toast'

export function Login() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [isSignUp, setIsSignUp] = useState(false)
  // Checkbox captcha state
  const [captchaId, setCaptchaId] = useState<string | null>(null)
  const [isCaptchaVerified, setIsCaptchaVerified] = useState(false)
  const [isVerifyingCaptcha, setIsVerifyingCaptcha] = useState(false)

  const initCaptcha = async () => {
    try {
      const data = await apiClient.getCaptcha()
      setCaptchaId(data.captcha_id)
      setIsCaptchaVerified(false)
    } catch (err) {
      console.error('Failed to init captcha:', err)
      // Fallback allows bypassing if backend is down (security tradeoff for UX)
      // In production you might want to block or show an error
      setCaptchaId('fallback')
    }
  }

  const handleCaptchaVerify = async () => {
    if (!captchaId || captchaId === 'fallback') {
      setIsCaptchaVerified(true)
      return
    }

    setIsVerifyingCaptcha(true)
    try {
      const result = await apiClient.verifyCaptcha(captchaId)
      if (result.verified) {
        setIsCaptchaVerified(true)
      }
    } catch (error) {
      console.error('Captcha verification failed:', error)
      toast.error('Verification failed. Please try again.')
      // Refresh token on failure
      initCaptcha()
    } finally {
      setIsVerifyingCaptcha(false)
    }
  }

  React.useEffect(() => {
    initCaptcha()
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)

    // Add password validation
    if (isSignUp) {
      // Stronger password requirements for registration
      if (password.length < 12) {
        toast.error('Password must be at least 12 characters long')
        setLoading(false)
        return
      }
      if (!/[A-Z]/.test(password)) {
        toast.error('Password must contain at least one uppercase letter')
        setLoading(false)
        return
      }
      if (!/[a-z]/.test(password)) {
        toast.error('Password must contain at least one lowercase letter')
        setLoading(false)
        return
      }
      if (!/\d/.test(password)) {
        toast.error('Password must contain at least one digit')
        setLoading(false)
        return
      }
      if (!/[!@#$%^&*(),.?":{}|<>]/.test(password)) {
        toast.error('Password must contain at least one special character')
        setLoading(false)
        return
      }
    } else {
      // Minimum validation for login (password already exists)
      if (password.length < 6) {
        toast.error('Password must be at least 6 characters')
        setLoading(false)
        return
      }
    }

    try {
      if (isSignUp) {
        await apiClient.register(username, password)
        toast.success('Account created successfully! You can now sign in.')
        setIsSignUp(false)
      } else {
        if (!isCaptchaVerified) {
          toast.error('Please verify you are not a robot')
          setLoading(false)
          return
        }
        await apiClient.login(username, password, captchaId || undefined)
        toast.success('Logged in successfully!')
        // Small delay to ensure token is stored
        setTimeout(() => navigate('/'), 100)
      }
    } catch (error) {
      console.error('Error:', error)
      toast.error(error instanceof Error ? error.message : (isSignUp ? 'Failed to create account' : 'Failed to log in'))
      // Refresh captcha on error
      if (!isSignUp) {
        initCaptcha()
        setIsCaptchaVerified(false)
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen gradient-animate flex items-center justify-center p-4">
      <div className="max-w-md w-full mx-auto bg-white/95 backdrop-blur-sm rounded-2xl shadow-2xl overflow-hidden border border-gray-200 fade-in">
        <div className="bg-gradient-to-br from-[#1F2937] via-[#111827] to-[#1F2937] p-8 text-center border-b-4 border-[#FDB80E] relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-r from-[#B91C1C]/20 to-transparent"></div>
          <div className="bg-gradient-to-br from-[#B91C1C] to-[#DC2626] w-16 h-16 rounded-xl flex items-center justify-center mx-auto mb-4 shadow-lg transform hover:rotate-0 transition-all duration-500 hover:scale-110 relative z-10 animate-float">
            <Wrench className="h-8 w-8 text-white" />
          </div>
          <h2 className="text-3xl font-bold text-white mb-2 font-heading tracking-wider relative z-10">LB AUTO REPAIR</h2>
          <p className="text-gray-300 text-sm tracking-wide uppercase relative z-10">Professional Dashboard Access</p>
        </div>

        <div className="p-8">
          <form className="space-y-6" onSubmit={handleSubmit}>
            <div>
              <label className="block text-sm font-bold text-gray-700 uppercase tracking-wide mb-2">
                Username
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                  <User className="h-5 w-5" />
                </div>
                <input
                  type="text"
                  required
                  className="pl-10 w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#B91C1C] focus:border-transparent outline-none transition-all focus:shadow-lg focus:shadow-[#B91C1C]/20 text-gray-900 placeholder:text-gray-500"
                  placeholder="Enter your username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-bold text-gray-700 uppercase tracking-wide mb-2">
                Password
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                  <Lock className="h-5 w-5" />
                </div>
                <input
                  type="password"
                  required
                  className="pl-10 w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#B91C1C] focus:border-transparent outline-none transition-all focus:shadow-lg focus:shadow-[#B91C1C]/20 text-gray-900 placeholder:text-gray-500"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
            </div>

            {!isSignUp && (
              <div className="bg-gray-50 p-4 rounded-lg border border-gray-200">
                <label className="block text-sm font-bold text-gray-700 uppercase tracking-wide mb-2">
                  Security Check
                </label>
                <div
                  onClick={!isCaptchaVerified && !isVerifyingCaptcha ? handleCaptchaVerify : undefined}
                  className={`
                    relative flex items-center p-4 rounded-md border-2 transition-all duration-300 cursor-pointer
                    ${isCaptchaVerified
                      ? 'bg-green-50 border-green-500 shadow-sm'
                      : 'bg-white border-gray-300 hover:border-blue-400 hover:shadow-md'
                    }
                  `}
                >
                  <div className={`
                    w-8 h-8 rounded border-2 flex items-center justify-center mr-4 transition-all duration-300
                    ${isCaptchaVerified
                      ? 'bg-green-500 border-green-500'
                      : isVerifyingCaptcha
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-400 bg-white'
                    }
                  `}>
                    {isCaptchaVerified ? (
                      <Check className="w-6 h-6 text-white animate-scale-in" />
                    ) : isVerifyingCaptcha ? (
                      <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />
                    ) : null}
                  </div>

                  <div className="flex flex-col select-none">
                    <span className={`text-sm font-medium ${isCaptchaVerified ? 'text-green-700' : 'text-gray-700'}`}>
                      {isCaptchaVerified ? "I'm verified" : "I'm not a robot"}
                    </span>
                    {isCaptchaVerified && (
                      <span className="text-xs text-green-600 font-bold tracking-wider">HUMAN CONFIRMED</span>
                    )}
                  </div>

                  <div className="absolute right-4 top-1/2 transform -translate-y-1/2">
                    <div className="w-8 h-8 opacity-20 hover:opacity-100 transition-opacity">
                      <Lock className="w-full h-full text-gray-600" />
                    </div>
                  </div>
                </div>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white font-bold py-3 px-4 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed group active:scale-95 shadow-lg hover:shadow-xl hover:shadow-blue-500/50 flex justify-center items-center gap-2"
            >
              {loading ? (
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
              ) : (
                <>
                  <span className="font-bold uppercase tracking-wide">Sign In to Dashboard</span>
                  <ArrowRight className="h-5 w-5 group-hover:translate-x-1 transition-transform" />
                </>
              )}
            </button>
          </form>
        </div>
        <div className="mt-4 text-center p-4 border-t border-gray-200">
          <button
            onClick={() => setIsSignUp(!isSignUp)}
            className="text-sm text-blue-600 hover:text-blue-500"
          >
            {isSignUp ? 'Already have an account? Sign in' : 'Need an account? Sign up'}
          </button>
        </div>
      </div>
    </div>
  )
}
export default Login
