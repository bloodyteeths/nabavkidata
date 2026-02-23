import Link from "next/link";
import { getAllPosts } from "@/lib/blog-posts";

export default function BlogPage() {
  const posts = getAllPosts();

  const categories = Array.from(new Set(posts.map((p) => p.category)));

  return (
    <main className="min-h-screen bg-background text-foreground">
      {/* Header */}
      <header className="border-b border-border bg-background/20">
        <div className="container mx-auto px-4 md:px-6 py-6">
          <Link
            href="/"
            className="text-sm text-muted-foreground hover:text-primary transition-colors"
          >
            &larr; Почетна
          </Link>
          <h1 className="text-3xl md:text-4xl font-bold mt-4">Блог</h1>
          <p className="text-muted-foreground mt-2 max-w-2xl">
            Анализи, водичи и инсајти за јавните набавки во Македонија.
          </p>
        </div>
      </header>

      <div className="container mx-auto px-4 md:px-6 py-10">
        {posts.length === 0 ? (
          <div className="text-center py-20">
            <p className="text-muted-foreground text-lg">
              Наскоро ќе бидат објавени нови статии.
            </p>
          </div>
        ) : (
          <>
            {categories.length > 1 ? (
              /* Grouped by category */
              <div className="space-y-12">
                {categories.map((category) => {
                  const categoryPosts = posts.filter(
                    (p) => p.category === category
                  );
                  return (
                    <section key={category}>
                      <h2 className="text-xl font-semibold mb-6 text-primary">
                        {category}
                      </h2>
                      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                        {categoryPosts.map((post) => (
                          <PostCard key={post.slug} post={post} />
                        ))}
                      </div>
                    </section>
                  );
                })}
              </div>
            ) : (
              /* Chronological listing */
              <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                {posts.map((post) => (
                  <PostCard key={post.slug} post={post} />
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </main>
  );
}

function PostCard({
  post,
}: {
  post: { slug: string; title: string; date: string; category: string; description: string };
}) {
  return (
    <Link
      href={`/blog/${post.slug}`}
      className="group block rounded-lg border border-border bg-secondary/30 p-6 hover:border-primary/50 hover:bg-secondary/50 transition-all"
    >
      <div className="flex items-center gap-3 text-xs text-muted-foreground mb-3">
        <span className="inline-block rounded-full bg-primary/10 text-primary px-2.5 py-0.5 font-medium">
          {post.category}
        </span>
        <time dateTime={post.date}>{post.date}</time>
      </div>
      <h3 className="text-lg font-semibold group-hover:text-primary transition-colors mb-2">
        {post.title}
      </h3>
      <p className="text-sm text-muted-foreground line-clamp-3">
        {post.description}
      </p>
    </Link>
  );
}
