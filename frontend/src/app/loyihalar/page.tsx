'use client';

import { useEffect, useState } from 'react';
import { Guard } from '@/components/Guard';
import { projects as projectsApi, type Project } from '@/lib/api';

const DIFFICULTY_STYLE: Record<string, string> = {
  Entry: 'bg-emerald-500/15 text-emerald-400',
  Pro: 'bg-amber-500/15 text-amber-400',
  Architect: 'bg-red-500/15 text-red-400',
};

function ProjectList() {
  const [items, setItems] = useState<Project[] | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    projectsApi
      .list()
      .then(setItems)
      .catch(() => setError('Loyihalarni yuklab bo‘lmadi'));
  }, []);

  if (error) return <p className="text-red-400 py-12 text-center">{error}</p>;
  if (!items) return <p className="text-slate-500 py-12 text-center">Yuklanmoqda...</p>;

  return (
    <>
      <h1 className="text-3xl font-extrabold mb-2">Loyihalar</h1>
      <p className="text-slate-400 mb-8 max-w-2xl leading-relaxed">
        Portfolio uchun amaliy loyihalar. Har birini o&apos;zingiz qilib
        ko&apos;ring — bu darsdan ko&apos;ra ko&apos;proq o&apos;rgatadi.
      </p>

      {items.length === 0 ? (
        <p className="text-slate-500 text-center py-12">Hozircha loyiha yo&apos;q.</p>
      ) : (
        <div className="grid sm:grid-cols-2 gap-5">
          {items.map((project) => (
            <article key={project.id} className="glass rounded-2xl overflow-hidden flex flex-col">
              {project.image_url && (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={project.image_url}
                  alt=""
                  loading="lazy"
                  className="w-full h-40 object-cover bg-slate-900"
                />
              )}

              <div className="p-5 flex-1 flex flex-col">
                <div className="flex items-start justify-between gap-3 mb-3">
                  <h2 className="font-bold text-lg min-w-0">{project.title}</h2>
                  <span
                    className={`px-2 py-1 rounded text-[11px] font-bold uppercase tracking-wider shrink-0 ${
                      DIFFICULTY_STYLE[project.difficulty] || 'bg-white/10 text-slate-400'
                    }`}
                  >
                    {project.difficulty}
                  </span>
                </div>

                {/*
                  Tavsif SERVERDA HTML ga aylantirilgan
                  (`core/richtext.py`) — matn ekranlangan va faqat
                  ruxsat etilgan teglar qo'yilgan.
                */}
                <div
                  className="lesson-prose text-sm mb-4 flex-1"
                  dangerouslySetInnerHTML={{ __html: project.description_html }}
                />

                {project.tech_list.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mb-4">
                    {project.tech_list.map((tech) => (
                      <span
                        key={tech}
                        className="px-2 py-1 rounded bg-white/5 text-[11px] text-slate-400"
                      >
                        {tech}
                      </span>
                    ))}
                  </div>
                )}

                {(project.demo_url || project.repo_url) && (
                  <div className="flex gap-3 text-sm pt-3 border-t border-white/5">
                    {project.demo_url && (
                      <a
                        href={project.demo_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary hover:underline"
                      >
                        Ko&apos;rish
                      </a>
                    )}
                    {project.repo_url && (
                      <a
                        href={project.repo_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-slate-400 hover:text-slate-200"
                      >
                        Kod
                      </a>
                    )}
                  </div>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
    </>
  );
}

export default function ProjectsPage() {
  return (
    <Guard>
      <ProjectList />
    </Guard>
  );
}
