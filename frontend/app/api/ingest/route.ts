import { NextRequest, NextResponse } from "next/server";
import { ingestDocument } from "@/lib/rag";

export async function POST(req: NextRequest) {
  const body = await req.json();
  const { source, title, content, organization, document_type, region } = body;

  if (!source || !title || !content)
    return NextResponse.json({ detail: "source, title, and content are required." }, { status: 400 });

  try {
    const chunks = await ingestDocument({
      source,
      title,
      content,
      organization: organization ?? "synthetic",
      documentType: document_type ?? "internal_procedure",
      region,
    });
    return NextResponse.json({ chunks_created: chunks.length });
  } catch (e) {
    return NextResponse.json({ detail: e instanceof Error ? e.message : String(e) }, { status: 500 });
  }
}
