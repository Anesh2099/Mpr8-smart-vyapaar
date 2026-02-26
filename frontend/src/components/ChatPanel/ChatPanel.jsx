import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ChevronRight,
  ChevronLeft,
  Send,
  Mic,
  Sparkles,
  Bot,
  User,
  AlertCircle,
  CheckCircle2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import useChatStore from '@/store/useChatStore';

const ChatPanel = () => {
  const {
    messages,
    isChatPanelOpen,
    toggleChatPanel,
    addMessage,
    activeAgents,
    isTyping,
    sendMessageToAgent
  } = useChatStore();

  const [inputValue, setInputValue] = useState('');
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const suggestedPrompts = [
    'Forecast next week sales',
    'Find best supplier',
    'Show low stock items',
    'Analyze top products',
  ];

  const handleSendMessage = () => {
    if (!inputValue.trim() || isTyping) return;

    sendMessageToAgent(inputValue);
    setInputValue('');
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      handleSendMessage();
    }
  };

  return (
    <AnimatePresence>
      {isChatPanelOpen && (
        <motion.aside
          initial={{ width: 0, opacity: 0 }}
          animate={{ width: '30%', opacity: 1 }}
          exit={{ width: 0, opacity: 0 }}
          transition={{ type: 'spring', damping: 25, stiffness: 200 }}
          className="min-w-[350px] h-screen bg-card border-l-2 border-accent/30 flex flex-col overflow-hidden"
        >
          {/* Header */}
          <div className="p-4 border-b border-border bg-gradient-to-r from-primary/10 to-accent/10">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <div className="relative">
                  <Bot className="h-6 w-6 text-primary" />
                  <div className="absolute -top-1 -right-1 w-2 h-2 bg-accent rounded-full animate-pulse"></div>
                </div>
                <h2 className="font-bold text-lg">AI Assistant</h2>
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={toggleChatPanel}
                className="h-8 w-8 hover:bg-accent/20"
              >
                <ChevronRight className="h-5 w-5" />
              </Button>
            </div>

            {/* Active Agents */}
            {activeAgents.length > 0 && (
              <div className="flex gap-2 flex-wrap mt-2">
                {activeAgents.map((agent) => (
                  <Badge key={agent} variant="secondary" className="text-xs">
                    <Sparkles className="h-3 w-3 mr-1" />
                    {agent}
                  </Badge>
                ))}
              </div>
            )}
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.map((message) => (
              <motion.div
                key={message.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className={`flex gap-3 ${message.role === 'user' ? 'flex-row-reverse' : ''
                  }`}
              >
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${message.role === 'user'
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-secondary'
                    }`}
                >
                  {message.role === 'user' ? (
                    <User className="h-4 w-4" />
                  ) : (
                    <Bot className="h-4 w-4" />
                  )}
                </div>
                <Card
                  className={`p-3 max-w-[85%] ${message.role === 'user'
                    ? 'bg-primary text-primary-foreground'
                    : message.isError
                      ? 'bg-destructive/10 border-destructive flex flex-col gap-2 text-destructive'
                      : 'bg-accent/10 border-accent/30 flex flex-col gap-3'
                    }`}
                >
                  <p className="text-sm whitespace-pre-wrap">{message.content}</p>

                  {/* Render Action Cards if they exist */}
                  {message.actionCards && message.actionCards.length > 0 && (
                    <div className="flex flex-col gap-2 mt-2 border-t pt-2 border-border/50">
                      {message.actionCards.map((card, idx) => (
                        <Card key={idx} className="p-3 bg-card border-primary/20 shadow-sm">
                          <div className="flex items-center gap-2 mb-2">
                            <CheckCircle2 className="w-4 h-4 text-primary" />
                            <span className="font-semibold text-xs uppercase text-primary tracking-wide">
                              {card.type.replace('_', ' ')}
                            </span>
                          </div>
                          <p className="text-sm text-foreground mb-3">{card.title}</p>
                          <div className="flex gap-2">
                            {card.actions && card.actions.map((act, i) => (
                              <Button key={i} size="sm" variant={i === 0 ? "default" : "outline"} className="flex-1 text-xs h-8">
                                {act.label}
                              </Button>
                            ))}
                          </div>
                        </Card>
                      ))}
                    </div>
                  )}

                  {/* Render Alerts if they exist */}
                  {message.alerts && message.alerts.length > 0 && (
                    <div className="flex flex-col gap-2 mt-1">
                      {message.alerts.map((alert, idx) => (
                        <div key={idx} className="flex items-start gap-2 bg-amber-500/10 text-amber-600 p-2 rounded-md border border-amber-500/20 text-xs">
                          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
                          <span>{alert.message}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </Card>
                <p className="text-xs opacity-70 mt-1">
                  {new Date(message.timestamp).toLocaleTimeString()}
                </p>
              </motion.div>
            ))}

            {/* Typing indicator */}
            {isTyping && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex gap-3"
              >
                <div className="w-8 h-8 rounded-full bg-secondary flex items-center justify-center shrink-0">
                  <Bot className="h-4 w-4" />
                </div>
                <Card className="p-3 bg-accent/10 border-accent/30 rounded-2xl rounded-tl-sm flex items-center gap-1">
                  <motion.div className="w-2 h-2 rounded-full bg-muted-foreground" animate={{ y: [0, -5, 0] }} transition={{ repeat: Infinity, duration: 0.6, delay: 0 }} />
                  <motion.div className="w-2 h-2 rounded-full bg-muted-foreground" animate={{ y: [0, -5, 0] }} transition={{ repeat: Infinity, duration: 0.6, delay: 0.2 }} />
                  <motion.div className="w-2 h-2 rounded-full bg-muted-foreground" animate={{ y: [0, -5, 0] }} transition={{ repeat: Infinity, duration: 0.6, delay: 0.4 }} />
                </Card>
              </motion.div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Suggested Prompts */}
          <div className="px-4 py-2 border-t border-border">
            <p className="text-xs text-muted-foreground mb-2">Suggested:</p>
            <div className="flex gap-2 flex-wrap">
              {suggestedPrompts.map((prompt) => (
                <Button
                  key={prompt}
                  variant="outline"
                  size="sm"
                  className="text-xs"
                  onClick={() => setInputValue(prompt)}
                >
                  {prompt}
                </Button>
              ))}
            </div>
          </div>

          {/* Input */}
          <div className="p-4 border-t border-border">
            <div className="flex gap-2">
              <Input
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Ask me anything..."
                className="flex-1"
              />
              <Button size="icon" onClick={handleSendMessage} disabled={!inputValue.trim() || isTyping}>
                <Send className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </motion.aside>
      )}
    </AnimatePresence>
  );
};

export default ChatPanel;
