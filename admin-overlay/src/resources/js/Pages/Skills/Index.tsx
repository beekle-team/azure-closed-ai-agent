import { Head } from "@inertiajs/react";
import { useEffect, useState } from "react";
import AuthenticatedLayout from "@/Layouts/AuthenticatedLayout";

type Skill = {
    id: string;
    name: string;
    description: string;
    approval: boolean;
};

export default function SkillsIndex({ agentUrl }: { agentUrl: string }) {
    const [skills, setSkills] = useState<Skill[]>([]);

    useEffect(() => {
        fetch(`${agentUrl}/v1/skills`)
            .then((response) => response.json())
            .then((payload: Skill[]) => setSkills(payload))
            .catch(() => setSkills([]));
    }, [agentUrl]);

    return (
        <AuthenticatedLayout
            header={<h2 className="text-xl font-semibold leading-tight text-gray-800">スキル</h2>}
        >
            <Head title="スキル" />

            <div className="py-8">
                <div className="mx-auto max-w-5xl space-y-4 sm:px-6 lg:px-8">
                    <p className="text-sm text-gray-600">
                        口伝を手順に書き換えたものがスキルです。中身は FastAPI のカタログから読みます。
                    </p>
                    {skills.map((skill) => (
                        <article key={skill.id} className="bg-white p-5 shadow-xs sm:rounded-lg">
                            <p className="text-xs text-gray-400">{skill.id}</p>
                            <h3 className="mt-1 text-lg font-medium text-gray-900">{skill.name}</h3>
                            <p className="mt-2 text-sm text-gray-700">{skill.description}</p>
                            <p className="mt-3 text-xs text-gray-500">
                                {skill.approval ? "実行前に承認が必要" : "承認なしで実行できる"}
                            </p>
                        </article>
                    ))}
                    {skills.length === 0 ? (
                        <p className="text-sm text-gray-500">agent.localhost からスキルを読めませんでした。</p>
                    ) : null}
                </div>
            </div>
        </AuthenticatedLayout>
    );
}
