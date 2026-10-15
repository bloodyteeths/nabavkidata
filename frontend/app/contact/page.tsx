'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Mail, Phone, Send, CheckCircle, AlertCircle } from 'lucide-react';
import Link from 'next/link';
import { api } from '@/lib/api';

export default function ContactPage() {
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    company: '',
    phone: '',
    message: ''
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
        plan: null
      });

      setSubmitted(true);
    } catch (err) {
      console.error('Contact form error:', err);
      setError('Грешка при испраќање. Ве молиме обидете се повторно или контактирајте нè директно на hello@nabavkidata.com');
    } finally {
      setLoading(false);
    }
  };

  if (submitted) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-gray-900 to-background flex items-center justify-center px-4">
        <div className="max-w-md text-center">
          <CheckCircle className="w-16 h-16 text-green-500 mx-auto mb-6" />
          <h1 className="text-2xl font-bold text-foreground mb-4">Благодариме!</h1>
          <p className="text-muted-foreground mb-8">
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
    <div className="min-h-screen bg-gradient-to-b from-gray-900 to-background py-16 px-4">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-3xl md:text-4xl font-bold text-foreground mb-4">
            Контактирајте нè
          </h1>
          <p className="text-muted-foreground max-w-xl mx-auto">
            Имате прашање? Пополнете го формуларот и ќе ви одговориме наскоро. Ако сакате ние да ја
            подготвиме вашата понуда, <Link href="/usluga?src=contact" className="text-primary underline underline-offset-4">нарачајте понуда</Link> или погледнете ги <Link href="/pricing" className="text-primary underline underline-offset-4">цените и условите</Link>.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-8">
          {/* Contact Info */}
          <div className="space-y-6">
            <div className="bg-foreground/5 border border-border rounded-xl p-6">
              <Mail className="w-6 h-6 text-primary mb-3" />
              <h3 className="text-foreground font-semibold mb-1">Email</h3>
              <a href="mailto:hello@nabavkidata.com" className="text-muted-foreground hover:text-primary transition-colors">
                hello@nabavkidata.com
              </a>
            </div>

            <div className="bg-foreground/5 border border-border rounded-xl p-6">
              <Phone className="w-6 h-6 text-primary mb-3" />
              <h3 className="text-foreground font-semibold mb-1">Телефон</h3>
              <a href="tel:+38970253467" className="text-muted-foreground hover:text-primary transition-colors">
                +389 70 253 467
              </a>
            </div>

          </div>

          {/* Contact Form */}
          <div className="md:col-span-2">
            <form onSubmit={handleSubmit} className="bg-foreground/5 border border-border rounded-xl p-8 space-y-6">
              {error && (
                <div className="flex items-center gap-3 p-4 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400">
                  <AlertCircle className="w-5 h-5 flex-shrink-0" />
                  <p className="text-sm">{error}</p>
                </div>
              )}
              <div className="grid md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-muted-foreground mb-2">
                    Име и презиме *
                  </label>
                  <Input
                    required
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    placeholder="Вашето име"
                    className="bg-foreground/5 border-border text-foreground placeholder:text-gray-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-muted-foreground mb-2">
                    Компанија
                  </label>
                  <Input
                    value={formData.company}
                    onChange={(e) => setFormData({ ...formData, company: e.target.value })}
                    placeholder="Име на компанија"
                    className="bg-foreground/5 border-border text-foreground placeholder:text-gray-500"
                  />
                </div>
              </div>

              <div className="grid md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-muted-foreground mb-2">
                    Email *
                  </label>
                  <Input
                    required
                    type="email"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    placeholder="email@example.com"
                    className="bg-foreground/5 border-border text-foreground placeholder:text-gray-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-muted-foreground mb-2">
                    Телефон
                  </label>
                  <Input
                    value={formData.phone}
                    onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                    placeholder="+389 7X XXX XXX"
                    className="bg-foreground/5 border-border text-foreground placeholder:text-gray-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-muted-foreground mb-2">
                  Порака *
                </label>
                <Textarea
                  required
                  rows={5}
                  value={formData.message}
                  onChange={(e) => setFormData({ ...formData, message: e.target.value })}
                  placeholder="Како можеме да ви помогнеме?"
                  className="bg-foreground/5 border-border text-foreground placeholder:text-gray-500 resize-none"
                />
              </div>

              <Button
                type="submit"
                disabled={loading}
                className="w-full bg-primary hover:bg-primary/90"
              >
                {loading ? (
                  <span className="flex items-center gap-2">
                    <span className="w-4 h-4 border-2 border-primary-foreground/30 border-t-primary-foreground rounded-full animate-spin" />
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
