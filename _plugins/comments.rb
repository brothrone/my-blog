require 'json'
Jekyll::Hooks.register :site, :post_write do |site|
  posts = site.posts.docs + site.collections.fetch('en_posts').docs
  threads = posts.map { |p| p.data['kr_permalink'] || p.url }.uniq
  source = File.read(File.join(site.source, 'server/comments-worker.js'))
  File.write(File.join(site.dest, '_worker.js'), source.sub('/* COMMENT_THREADS */ []', JSON.generate(threads)))
  File.write(File.join(site.dest, '_routes.json'), JSON.generate({'version'=>1, 'include'=>['/api/comments','/api/comment-admin'], 'exclude'=>[]}))
end
