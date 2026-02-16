import { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  getAllPosts,
  getPostBySlug,
  getRelatedPosts,
} from "@/lib/blog-posts";

interface BlogPostPageProps {
  params: { slug: string };
}

export function generateStaticParams() {
  return getAllPosts().map((post) => ({ slug: post.slug }));
}

export function generateMetadata({ params }: BlogPostPageProps): Metadata {
  const post = getPostBySlug(params.slug);
  if (!post) {
    return { title: "Статијата не е пронајдена" };
  }
  return {
    title: post.title,
    description: post.description,
    openGraph: {
      title: post.title,
      description: post.description,
      type: "article",
      publishedTime: post.date,
      authors: [post.author],
    },
  };
}

export default function BlogPostPage({ params }: BlogPostPageProps) {
  const post = getPostBySlug(params.slug);
  if (!post) {
    notFound();
  }

  const relatedPosts = getRelatedPosts(params.slug);

  return (
    <main className="min-h-screen bg-background text-foreground">
      {/* Header */}
      <header className="border-b border-white/10 bg-black/20">
        <div className="container mx-auto px-4 md:px-6 py-6">
          <Link
            href="/blog"
            className="text-sm text-muted-foreground hover:text-primary transition-colors"
          >
            &larr; Назад кон блог
          </Link>
        </div>
      </header>

      <article className="container mx-auto px-4 md:px-6 py-10 max-w-3xl">
        {/* Meta */}
        <div className="flex items-center gap-3 text-sm text-muted-foreground mb-4">
          <span className="inline-block rounded-full bg-primary/10 text-primary px-2.5 py-0.5 text-xs font-medium">
            {post.category}
          </span>
          <time dateTime={post.date}>{post.date}</time>
          <span>|</span>
          <span>{post.author}</span>
        </div>

        {/* Title */}
        <h1 className="text-3xl md:text-4xl font-bold mb-8 leading-tight">
          {post.title}
        </h1>

        {/* Content */}
        <div
          className="blog-content space-y-5 text-muted-foreground leading-relaxed
            [&_h2]:text-2xl [&_h2]:font-semibold [&_h2]:text-foreground [&_h2]:mt-10 [&_h2]:mb-4
            [&_h3]:text-xl [&_h3]:font-semibold [&_h3]:text-foreground [&_h3]:mt-8 [&_h3]:mb-3
            [&_h4]:text-lg [&_h4]:font-medium [&_h4]:text-foreground [&_h4]:mt-6 [&_h4]:mb-2
            [&_p]:mb-4
            [&_ul]:list-disc [&_ul]:pl-6 [&_ul]:space-y-2
            [&_ol]:list-decimal [&_ol]:pl-6 [&_ol]:space-y-2
            [&_li]:text-muted-foreground
            [&_a]:text-primary [&_a]:underline [&_a]:hover:text-primary/80
            [&_strong]:text-foreground [&_strong]:font-semibold
            [&_blockquote]:border-l-4 [&_blockquote]:border-primary/50 [&_blockquote]:pl-4 [&_blockquote]:italic [&_blockquote]:text-muted-foreground/80
            [&_code]:bg-secondary [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:rounded [&_code]:text-sm [&_code]:text-primary
            [&_pre]:bg-secondary [&_pre]:p-4 [&_pre]:rounded-lg [&_pre]:overflow-x-auto
            [&_table]:w-full [&_table]:border-collapse
            [&_th]:border [&_th]:border-border [&_th]:px-3 [&_th]:py-2 [&_th]:text-left [&_th]:bg-secondary/50 [&_th]:text-foreground [&_th]:font-medium
            [&_td]:border [&_td]:border-border [&_td]:px-3 [&_td]:py-2
            [&_hr]:border-border [&_hr]:my-8"
          dangerouslySetInnerHTML={{ __html: post.content }}
        />
      </article>

      {/* Related Posts */}
      {relatedPosts.length > 0 && (
        <section className="border-t border-white/10 bg-black/10">
          <div className="container mx-auto px-4 md:px-6 py-10 max-w-3xl">
            <h2 className="text-xl font-semibold mb-6">Поврзани статии</h2>
            <div className="grid gap-4 sm:grid-cols-2">
              {relatedPosts.map((related) => (
                <Link
                  key={related.slug}
                  href={`/blog/${related.slug}`}
                  className="group block rounded-lg border border-border bg-secondary/30 p-5 hover:border-primary/50 hover:bg-secondary/50 transition-all"
                >
                  <div className="flex items-center gap-2 text-xs text-muted-foreground mb-2">
                    <span className="inline-block rounded-full bg-primary/10 text-primary px-2 py-0.5 font-medium">
                      {related.category}
                    </span>
                    <time dateTime={related.date}>{related.date}</time>
                  </div>
                  <h3 className="font-semibold group-hover:text-primary transition-colors">
                    {related.title}
                  </h3>
                </Link>
              ))}
            </div>
          </div>
        </section>
      )}
    </main>
  );
}
