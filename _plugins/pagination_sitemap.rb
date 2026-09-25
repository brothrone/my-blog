# 홈 목록 2페이지 이후(/page/2/ 등)는 noindex 로 두므로 사이트맵에서도 뺀다.
# noindex 페이지가 사이트맵에 있으면 Search Console 에 "제출된 URL에 noindex 태그" 오류가 뜬다.
# jekyll-paginate 가 만든 페이지는 실제 파일이 없어 _config.yml defaults 로는 걸러지지 않는다.
Jekyll::Hooks.register :site, :pre_render do |site|
  site.pages.each do |page|
    page.data['sitemap'] = false if page.pager && page.pager.page > 1
  end
end
