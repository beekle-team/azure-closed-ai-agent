import { Head } from "@inertiajs/react";
import AuthenticatedLayout from "@/Layouts/AuthenticatedLayout";

type Organization = {
    name: string;
    plan: string;
    monthly_token_limit: number;
    tokens_used: number;
    remaining_tokens: number;
};

type UsageEvent = {
    id: number;
    user: string | null;
    model: string;
    tokens: number;
    created_at: string | null;
};

export default function UsageIndex({
    organization,
    events,
}: {
    organization: Organization | null;
    events: UsageEvent[];
}) {
    return (
        <AuthenticatedLayout
            header={<h2 className="text-xl font-semibold leading-tight text-gray-800">利用状況</h2>}
        >
            <Head title="利用状況" />

            <div className="py-12">
                <div className="mx-auto max-w-7xl space-y-6 sm:px-6 lg:px-8">
                    <div className="bg-white p-6 shadow-xs sm:rounded-lg">
                        {organization ? (
                            <dl className="grid gap-4 sm:grid-cols-2">
                                <div>
                                    <dt className="text-sm text-gray-500">組織</dt>
                                    <dd className="mt-1 text-lg font-medium">{organization.name}</dd>
                                </div>
                                <div>
                                    <dt className="text-sm text-gray-500">プラン</dt>
                                    <dd className="mt-1 text-lg font-medium">{organization.plan}</dd>
                                </div>
                                <div>
                                    <dt className="text-sm text-gray-500">今月の使用</dt>
                                    <dd className="mt-1 text-lg font-medium">
                                        {organization.tokens_used.toLocaleString()} /{" "}
                                        {organization.monthly_token_limit.toLocaleString()}
                                    </dd>
                                </div>
                                <div>
                                    <dt className="text-sm text-gray-500">残り</dt>
                                    <dd className="mt-1 text-lg font-medium">
                                        {organization.remaining_tokens.toLocaleString()}
                                    </dd>
                                </div>
                            </dl>
                        ) : (
                            <p className="text-gray-700">組織がまだ紐づいていません。</p>
                        )}
                    </div>

                    <div className="overflow-hidden bg-white shadow-xs sm:rounded-lg">
                        <table className="min-w-full divide-y divide-gray-200 text-sm">
                            <thead className="bg-gray-50">
                                <tr>
                                    <th className="px-4 py-3 text-left font-medium text-gray-600">日時</th>
                                    <th className="px-4 py-3 text-left font-medium text-gray-600">利用者</th>
                                    <th className="px-4 py-3 text-left font-medium text-gray-600">モデル</th>
                                    <th className="px-4 py-3 text-right font-medium text-gray-600">トークン</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-100">
                                {events.map((event) => (
                                    <tr key={event.id}>
                                        <td className="px-4 py-3">{event.created_at}</td>
                                        <td className="px-4 py-3">{event.user}</td>
                                        <td className="px-4 py-3">{event.model}</td>
                                        <td className="px-4 py-3 text-right">{event.tokens.toLocaleString()}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </AuthenticatedLayout>
    );
}
