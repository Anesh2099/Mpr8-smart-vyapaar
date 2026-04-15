import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  TrendingUp,
  Users,
  Sparkles,
  BarChart3,
  ShoppingCart,
  Bot,
  CheckCircle,
  ArrowRight,
} from 'lucide-react';

const Landing = () => {
  const features = [
    {
      icon: TrendingUp,
      title: 'AI-Powered Forecasting',
      description: 'Predict demand and optimize inventory with machine learning algorithms.',
    },
    {
      icon: Users,
      title: 'Supplier Negotiation',
      description: 'Let AI agents negotiate best prices and terms with your suppliers.',
    },
    {
      icon: Sparkles,
      title: 'Smart Insights',
      description: 'Get real-time recommendations to boost sales and reduce waste.',
    },
  ];

  const testimonials = [
    {
      name: 'Rajesh Kumar',
      role: 'Grocery Store Owner',
      content: 'VendorAI helped me reduce waste by 40% and increase profits by 25%!',
    },
    {
      name: 'Priya Sharma',
      role: 'Electronics Retailer',
      content: 'The AI forecasting is incredibly accurate. I never run out of stock now.',
    },
    {
      name: 'Mohammed Ali',
      role: 'Pharmacy Owner',
      content: 'Automated supplier negotiation saves me hours every week. Highly recommend!',
    },
  ];

  const faqs = [
    {
      question: 'How does AI forecasting work?',
      answer: 'Our AI analyzes your historical sales data, seasonal trends, and market conditions to predict future demand.',
    },
    {
      question: 'Is my data secure?',
      answer: 'Yes! We use bank-grade encryption and never share your data with third parties.',
    },
    {
      question: 'Can I customize the AI agents?',
      answer: 'Absolutely! You can configure agent permissions and automation levels in settings.',
    },
  ];

  return (
    <div className="min-h-screen bg-background">
      {/* Hero Section */}
      <section className="relative overflow-hidden bg-gradient-to-br from-primary/10 via-background to-secondary/10">
        <div className="container mx-auto px-4 py-20">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            className="text-center max-w-4xl mx-auto"
          >
            <div className="inline-flex items-center gap-2 bg-primary/10 px-4 py-2 rounded-full mb-6">
              <Bot className="h-5 w-5 text-primary" />
              <span className="text-sm font-medium">Powered by Agentic AI</span>
            </div>
            
            <h1 className="text-5xl md:text-6xl font-bold mb-6 bg-clip-text text-transparent bg-gradient-to-r from-primary via-accent to-primary">
              Smart Vyapar: AI Business OS for Local Shopkeepers
            </h1>
            
            <p className="text-xl text-muted-foreground mb-8">
              Transform your shop with AI-powered inventory management, demand forecasting, and automated supplier negotiations. Like ChatGPT, but built for your business.
            </p>
            
            <div className="flex gap-4 justify-center flex-wrap">
              <Link to="/dashboard">
                <Button size="lg" className="gap-2">
                  Get Started <ArrowRight className="h-5 w-5" />
                </Button>
              </Link>
              <Button size="lg" variant="outline">
                Watch Demo
              </Button>
            </div>
          </motion.div>

          {/* Animated Dashboard Preview */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.3, duration: 0.8 }}
            className="mt-16 max-w-5xl mx-auto"
          >
            <Card className="overflow-hidden shadow-2xl border-2">
              <div className="bg-gradient-to-r from-primary/20 to-secondary/20 p-8">
                <div className="grid grid-cols-3 gap-4">
                  <Card>
                    <CardHeader className="pb-3">
                      <CardTitle className="text-sm">Today's Sales</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <p className="text-2xl font-bold">₹45,231</p>
                      <p className="text-xs text-green-600">+12% from yesterday</p>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardHeader className="pb-3">
                      <CardTitle className="text-sm">Low Stock Items</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <p className="text-2xl font-bold">8</p>
                      <p className="text-xs text-orange-600">Reorder recommended</p>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardHeader className="pb-3">
                      <CardTitle className="text-sm">AI Insights</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <p className="text-2xl font-bold">23</p>
                      <p className="text-xs text-blue-600">New recommendations</p>
                    </CardContent>
                  </Card>
                </div>
              </div>
            </Card>
          </motion.div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-20 bg-muted/30">
        <div className="container mx-auto px-4">
          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            className="text-center mb-12"
          >
            <h2 className="text-4xl font-bold mb-4">Powerful AI Features</h2>
            <p className="text-muted-foreground text-lg">Everything you need to run a smarter retail business</p>
          </motion.div>

          <div className="grid md:grid-cols-3 gap-8 max-w-6xl mx-auto">
            {features.map((feature, index) => {
              const Icon = feature.icon;
              return (
                <motion.div
                  key={index}
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: index * 0.2 }}
                >
                  <Card className="h-full hover:shadow-lg transition-shadow">
                    <CardHeader>
                      <div className="w-12 h-12 bg-primary/10 rounded-lg flex items-center justify-center mb-4">
                        <Icon className="h-6 w-6 text-primary" />
                      </div>
                      <CardTitle>{feature.title}</CardTitle>
                      <CardDescription>{feature.description}</CardDescription>
                    </CardHeader>
                  </Card>
                </motion.div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Testimonials Section */}
      <section className="py-20">
        <div className="container mx-auto px-4">
          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            className="text-center mb-12"
          >
            <h2 className="text-4xl font-bold mb-4">Trusted by Local Businesses</h2>
            <p className="text-muted-foreground text-lg">See what our users say about us</p>
          </motion.div>

          <div className="grid md:grid-cols-3 gap-8 max-w-6xl mx-auto">
            {testimonials.map((testimonial, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: index * 0.2 }}
              >
                <Card>
                  <CardContent className="pt-6">
                    <p className="text-muted-foreground mb-4">"{testimonial.content}"</p>
                    <div>
                      <p className="font-semibold">{testimonial.name}</p>
                      <p className="text-sm text-muted-foreground">{testimonial.role}</p>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ Section */}
      <section className="py-20 bg-muted/30">
        <div className="container mx-auto px-4 max-w-4xl">
          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            className="text-center mb-12"
          >
            <h2 className="text-4xl font-bold mb-4">Frequently Asked Questions</h2>
          </motion.div>

          <div className="space-y-4">
            {faqs.map((faq, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, x: -20 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ delay: index * 0.1 }}
              >
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg flex items-start gap-2">
                      <CheckCircle className="h-5 w-5 text-primary mt-1 shrink-0" />
                      {faq.question}
                    </CardTitle>
                    <CardDescription className="ml-7">{faq.answer}</CardDescription>
                  </CardHeader>
                </Card>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 bg-primary text-primary-foreground">
        <div className="container mx-auto px-4 text-center">
          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
          >
            <h2 className="text-4xl font-bold mb-4">Ready to Join the AI Revolution?</h2>
            <p className="text-lg mb-8 opacity-90">Start using AI agents today and see results within days.</p>
            <Link to="/dashboard">
              <Button size="lg" variant="secondary" className="gap-2">
                Get Started Now <ArrowRight className="h-5 w-5" />
              </Button>
            </Link>
          </motion.div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-8 border-t border-border">
        <div className="container mx-auto px-4 text-center text-muted-foreground">
          <p>© 2024 Smart Vyapar - AI Business OS for Local Retailers. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
};

export default Landing;
