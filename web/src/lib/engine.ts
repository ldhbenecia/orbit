// 엔진 API 는 이 기기(루프백)에서만 열림 — 브라우저가 아니라 Next 서버가 부름
export const ENGINE_URL = process.env.ORBIT_API_URL ?? "http://127.0.0.1:8000";

export async function engineJson<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${ENGINE_URL}${path}`);
    if (!res.ok) {
      console.error(`엔진 API ${path} 응답 ${res.status}`);
      return null;
    }
    return (await res.json()) as T;
  } catch (error) {
    console.error(`엔진 API ${path} 요청 실패`, error);
    return null;
  }
}
