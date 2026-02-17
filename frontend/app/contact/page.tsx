'use client';

import { useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Building2, Mail, Phone, Send, CheckCircle, AlertCircle } from 'lucide-react';
import Link from 'next/link';
import { api } from '@/lib/api';

export default function ContactPage() {
  const searchParams = useSearchParams();
  const plan = searchParams.get('plan');
  const isEnterprise = plan === 'enterprise';

  const [formData, setFormData] = useState({
    name: '',
    email: '',
    company: '',
    phone: '',
    message: isEnterprise
      ? 'Заинтересирани сме за Enterprise планот. Ве молиме контактирајте не за повеќе информации.'
      : ''
  });
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      await api.submitContactForm({
        name: formData.name,
        email: formData.email,
        company: formData.company || null,
        phone: formData.phone || null,
        message: formData.message,
        plan: isEnterprise ? 'enterprise' : null
      });

      setSubmitted(true);
    } catch (err) {
      console.error('Contact form error:', err);
      setError('Грешка при испраќање. Ве молиме обидете се повторно или контактирајте не директно на support@nabavkidata.com');
    } finally {
      setLoading(false);
    }
  };

  if (submitted) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-gray-900 to-black flex items-center justify-center px-4">
        <div className="max-w-md text-center">
          <CheckCircle className="w-16 h-16 text-green-500 mx-auto mb-6" />
          <h1 className="text-2xl font-bold text-white mb-4">Благодариме!</h1>
          <p className="text-gray-400 mb-8">
            Вашата порака е успешно испратена. Ќе ви одговориме наскоро.
          </p>
          <Link href="/">
            <Button>Назад кон почетна</Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-900 to-black py-16 px-4">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="text-center mb-12">
          {isEnterprise && (
            <div className="inline-flex items-center gap-2 bg-primary/20 text-primary px-4 py-2 rounded-full mb-6">
              <Building2 className="w-4 h-4" />
              <span className="text-sm font-medium">Enterprise Plan</span>
            </div>
          )}
          <h1 className="text-3xl md:text-4xl font-bold text-white mb-4">
            {isEnterprise ? 'Enterprise решение' : 'Контактирајте не'}
          </h1>
          <p className="text-gray-400 max-w-xl mx-auto">
            {isEnterprise
              ? 'Добијте прилагодено решение за вашата организација со неограничен пристап, API интеграција и посветен менаџер.'
              : 'Имате прашање? Пополнете го формуларот и ќе ви одговориме наскоро.'}
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-8">
          {/* Contact Info */}
          <div className="space-y-6">
            <div className="bg-white/5 border border-white/10 rounded-xl p-6">
              <Mail className="w-6 h-6 text-primary mb-3" />
              <h3 className="text-white font-semibold mb-1">Email</h3>
              <a href="mailto:support@nabavkidata.com" className="text-gray-400 hover:text-primary transition-colors">
                support@nabavkidata.com
              </a>
            </div>

            <div className="bg-white/5 border border-white/10 rounded-xl p-6">
              <Phone className="w-6 h-6 text-primary mb-3" />
              <h3 className="text-white font-semibold mb-1">Телефон</h3>
              <a href="tel:+38976355089" className="text-gray-400 hover:text-primary transition-colors">
                +389 76 355 089
              </a>
            </div>

            {isEnterprise && (
              <div className="bg-primary/10 border border-primary/30 rounded-xl p-6">
                <h3 className="text-white font-semibold mb-3">Enterprise вклучува:</h3>
                <ul className="space-y-2 text-gray-300 text-sm">
                  <li>• 1000 AI прашања дневно</li>
                  <li>• API пристап</li>
                  <li>• До 10 членови на тим</li>
                  <li>• Посветен менаџер</li>
                  <li>• SLA гаранција</li>
                  <li>• Приоритетна поддршка</li>
                </ul>
              </div>
            )}
          </div>

          {/* Contact Form */}
          <div className="md:col-span-2">
            <form onSubmit={handleSubmit} className="bg-white/5 border border-white/10 rounded-xl p-8 space-y-6">
              {error && (
                <div className="flex items-center gap-3 p-4 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400">
                  <AlertCircle className="w-5 h-5 flex-shrink-0" />
                  <p className="text-sm">{error}</p>
                </div>
              )}
              <div className="grid md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Име и презиме *
                  </label>
                  <Input
                    required
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    placeholder="Вашето име"
                    className="bg-white/5 border-white/10 text-white placeholder:text-gray-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Компанија
                  </label>
                  <Input
                    value={formData.company}
                    onChange={(e) => setFormData({ ...formData, company: e.target.value })}
                    placeholder="Име на компанија"
                    className="bg-white/5 border-white/10 text-white placeholder:text-gray-500"
                  />
                </div>
              </div>

              <div className="grid md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Email *
                  </label>
                  <Input
                    required
                    type="email"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    placeholder="email@example.com"
                    className="bg-white/5 border-white/10 text-white placeholder:text-gray-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Телефон
                  </label>
                  <Input
                    value={formData.phone}
                    onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                    placeholder="+389 7X XXX XXX"
                    className="bg-white/5 border-white/10 text-white placeholder:text-gray-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Порака *
                </label>
                <Textarea
                  required
                  rows={5}
                  value={formData.message}
                  onChange={(e) => setFormData({ ...formData, message: e.target.value })}
                  placeholder="Како можеме да ви помогнеме?"
                  className="bg-white/5 border-white/10 text-white placeholder:text-gray-500 resize-none"
                />
              </div>

              <Button
                type="submit"
                disabled={loading}
                className="w-full bg-primary hover:bg-primary/90"
              >
                {loading ? (
                  <span className="flex items-center gap-2">
                    <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Се испраќа...
                  </span>
                ) : (
                  <span className="flex items-center gap-2">
                    <Send className="w-4 h-4" />
                    Испрати порака
                  </span>
                )}
              </Button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
