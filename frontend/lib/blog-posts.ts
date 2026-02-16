import { batch1Posts } from './blog-posts-batch1';
import { batch2Posts } from './blog-posts-batch2';
import { batch3Posts } from './blog-posts-batch3';

export interface BlogPost {
  slug: string;
  title: string;
  description: string;
  date: string;
  author: string;
  category: string;
  content: string;
  relatedSlugs: string[];
}

const posts: BlogPost[] = [...batch1Posts, ...batch2Posts, ...batch3Posts];

export function getAllPosts(): BlogPost[] {
  return [...posts].sort(
    (a, b) => new Date(b.date).getTime() - new Date(a.date).getTime()
  );
}

export function getPostBySlug(slug: string): BlogPost | undefined {
  return posts.find((post) => post.slug === slug);
}

export function getRelatedPosts(slug: string): BlogPost[] {
  const post = getPostBySlug(slug);
  if (!post) return [];
  return post.relatedSlugs
    .map((relatedSlug) => getPostBySlug(relatedSlug))
    .filter((p): p is BlogPost => p !== undefined);
}
