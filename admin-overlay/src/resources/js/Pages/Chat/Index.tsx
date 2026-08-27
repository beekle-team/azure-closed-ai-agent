import { Head } from "@inertiajs/react";
import { FormEvent, useEffect, useState } from "react";
import AuthenticatedLayout from "@/Layouts/AuthenticatedLayout";

type Skill = {
    id: string;
    name: string;
    description: string;
    approval: boolean;
};

type Citation = {
    name: string;
    kind: string;
    reason: string;
    source: string;
};

type ChatResponse = {
    status: string;
    answer: string;
    citations: Citation[];
    remaining_tokens: number | null;
    approval_id: string | null;
    skill_id: string | null;
    plan: string[];
};

type Message = {
    role: "user" | "agent";
    text: string;
    meta?: string;
};

const STARTERS = [
    "海外出張の申請、画面に出てこない確認事項は？",
    "金属の大型稟議は誰に先に話す？",
    "初めての取引先の与信ルートは？",
    "出張事前チェックを回して",
];

export default function ChatIndex({
    agentUrl,
    userId,
}: {
    agentUrl: string;
    userId: number;
}) {
    const [skills, setSkills] = useState<Skill[]>([]);
    const [messages, setMessages] = useState<Message[]>([]);
    const [question, setQuestion] = useState("");
    const [busy, setBusy] = useState(false);

    useEffect(() => {
        fetch(`${agentUrl}/v1/skills`)
            .then((response) => response.json())
            .then((payload: Skill[]) => setSkills(payload))
            .catch(() => setSkills([]));
    }, [agentUrl]);

    async function ask(text: string) {
        const trimmed = text.trim();
        if (!trimmed || busy) {
            return;
        }
        setBusy(true);
        setQuestion("");
        setMessages((current) => [...current, { role: "user", text: trimmed }]);
        try {
            const response = await fetch(`${agentUrl}/v1/chat`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ user_id: userId, question: trimmed }),
            });
            const payload = (await response.json()) as ChatResponse;
            const cites = (payload.citations || []).map((cite) => `${cite.source} / ${cite.name}`).join(" · ");
            const plan = (payload.plan || []).join(", ");
            setMessages((current) => [
                ...current,
                {
                    role: "agent",
                    text: payload.answer,
                    meta: [payload.status, plan, cites].filter(Boolean).join("  |  "),
                },
            ]);
        } catch {
            setMessages((current) => [
                ...current,
                { role: "agent", text: "エージェントに届きませんでした。agent.localhost を確認してください。" },
            ]);
        } finally {
            setBusy(false);
        }
    }

    function onSubmit(event: FormEvent) {
        event.preventDefault();
        void ask(question);
    }

    return (
        <AuthenticatedLayout
            header={<h2 className="text-xl font-semibold leading-tight text-gray-800">社内AIチャット</h2>}
        >
            <Head title="社内AIチャット" />

            <div className="py-8">
                <div className="mx-auto grid max-w-7xl gap-6 lg:grid-cols-[280px_1fr] sm:px-6 lg:px-8">
                    <aside className="space-y-4 bg-white p-5 shadow-xs sm:rounded-lg">
                        <p className="text-xs tracking-wide text-amber-700">デモ商事 · 口伝をスキルにする</p>
                        <div>
                            <p className="mb-2 text-xs font-medium text-gray-500">スキル</p>
                            <div className="space-y-2">
                                {skills.map((skill) => (
                                    <button
                                        key={skill.id}
                                        type="button"
                                        className="block w-full rounded-md border border-gray-200 px-3 py-2 text-left hover:bg-gray-50"
                                        onClick={() => void ask(`${skill.name}を回して`)}
                                    >
                                        <span className="block text-sm font-medium text-gray-900">{skill.name}</span>
                                        <span className="block text-xs text-gray-500">{skill.description}</span>
                                    </button>
                                ))}
                            </div>
                        </div>
                        <div>
                            <p className="mb-2 text-xs font-medium text-gray-500">聞いてみる</p>
                            <div className="space-y-2">
                                {STARTERS.map((starter) => (
                                    <button
                                        key={starter}
                                        type="button"
                                        className="block w-full rounded-md border border-gray-200 px-3 py-2 text-left text-sm text-gray-700 hover:bg-gray-50"
                                        onClick={() => void ask(starter)}
                                    >
                                        {starter}
                                    </button>
                                ))}
                            </div>
                        </div>
                    </aside>

                    <section className="flex min-h-[480px] flex-col bg-white shadow-xs sm:rounded-lg">
                        <div className="flex-1 space-y-4 overflow-auto p-6">
                            {messages.length === 0 ? (
                                <p className="text-sm text-gray-500">
                                    画面に無い確認を聞いてください。回答は FastAPI の検索計画とスキルから返ります。
                                </p>
                            ) : (
                                messages.map((message, index) => (
                                    <div key={`${message.role}-${index}`}>
                                        <p className="text-xs text-gray-500">
                                            {message.role === "user" ? "あなた" : "社内AIチャット"}
                                        </p>
                                        <pre className="mt-1 whitespace-pre-wrap font-sans text-sm text-gray-900">
                                            {message.text}
                                        </pre>
                                        {message.meta ? (
                                            <p className="mt-1 text-xs text-gray-400">{message.meta}</p>
                                        ) : null}
                                    </div>
                                ))
                            )}
                        </div>
                        <form onSubmit={onSubmit} className="flex gap-2 border-t border-gray-100 p-4">
                            <input
                                value={question}
                                onChange={(event) => setQuestion(event.target.value)}
                                className="flex-1 rounded-md border-gray-300 shadow-xs"
                                placeholder="業務の聞き方で投げる"
                                disabled={busy}
                            />
                            <button
                                type="submit"
                                disabled={busy}
                                className="rounded-md bg-gray-800 px-4 py-2 text-sm text-white disabled:opacity-50"
                            >
                                送る
                            </button>
                        </form>
                    </section>
                </div>
            </div>
        </AuthenticatedLayout>
    );
}
