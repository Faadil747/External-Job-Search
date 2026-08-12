"use client";

import * as React from "react";
import { Bot, Loader2, Send, Sparkles, User as UserIcon, WrenchIcon } from "lucide-react";

import { RouteGuard } from "@/components/route-guard";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { EmptyState } from "@/components/empty-state";
import { ApiError, aiApi } from "@/lib/api";
import { cn } from "@/lib/utils";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
}

export default function AssistantPage() {
  return (
    <RouteGuard>
      <AssistantContent />
    </RouteGuard>
  );
}

function AssistantContent() {
  const [messages, setMessages] = React.useState<ChatMessage[]>([]);
  const [input, setInput] = React.useState("");
  const [sending, setSending] = React.useState(false);
  const [unavailable, setUnavailable] = React.useState(false);
  const scrollRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || sending) return;

    const userMessage: ChatMessage = { id: crypto.randomUUID(), role: "user", content: text };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setSending(true);

    try {
      const res = await aiApi.chat({ message: text });
      setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: "assistant", content: res.reply }]);
    } catch (err) {
      if (err instanceof ApiError && (err.status === 404 || err.status === 501)) {
        setUnavailable(true);
      } else {
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: "assistant",
            content:
              err instanceof ApiError && err.status === 503
                ? "The AI assistant is temporarily unavailable. Please try again shortly."
                : "Something went wrong reaching the assistant. Please try again.",
          },
        ]);
      }
    } finally {
      setSending(false);
    }
  }

  if (unavailable) {
    return (
      <div className="container max-w-2xl py-16">
        <EmptyState
          icon={<WrenchIcon className="h-5 w-5" />}
          title="AI Career Assistant is coming soon"
          description="This feature isn't available yet. Check back soon — in the meantime, explore your resume analysis and matched jobs."
        />
      </div>
    );
  }

  return (
    <div className="container flex h-[calc(100vh-4rem)] max-w-3xl flex-col py-6">
      <div className="mb-4">
        <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight text-foreground">
          <Sparkles className="h-5 w-5 text-primary" /> AI Career Assistant
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Ask about your resume, a specific job, or general career advice.
        </p>
      </div>

      <Card className="flex flex-1 flex-col overflow-hidden">
        <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto p-5">
          {messages.length === 0 && (
            <div className="flex h-full flex-col items-center justify-center text-center text-muted-foreground">
              <Bot className="mb-3 h-8 w-8" />
              <p className="text-sm">Start the conversation — ask anything about your job search.</p>
            </div>
          )}
          {messages.map((m) => (
            <div key={m.id} className={cn("flex items-start gap-3", m.role === "user" && "flex-row-reverse")}>
              <div
                className={cn(
                  "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
                  m.role === "user" ? "bg-secondary text-secondary-foreground" : "bg-primary-100 text-primary"
                )}
              >
                {m.role === "user" ? <UserIcon className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
              </div>
              <div
                className={cn(
                  "max-w-[75%] rounded-2xl px-4 py-2.5 text-sm",
                  m.role === "user" ? "bg-secondary text-secondary-foreground" : "bg-muted text-foreground"
                )}
              >
                {m.content}
              </div>
            </div>
          ))}
          {sending && (
            <div className="flex items-start gap-3">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary-100 text-primary">
                <Bot className="h-4 w-4" />
              </div>
              <div className="flex items-center gap-2 rounded-2xl bg-muted px-4 py-2.5 text-sm text-muted-foreground">
                <Loader2 className="h-3.5 w-3.5 animate-spin" /> Thinking…
              </div>
            </div>
          )}
        </div>

        <CardContent className="border-t border-border p-3">
          <form onSubmit={handleSend} className="flex gap-2">
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask the AI assistant…"
              disabled={sending}
            />
            <Button type="submit" size="icon" disabled={sending || !input.trim()}>
              <Send className="h-4 w-4" />
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
