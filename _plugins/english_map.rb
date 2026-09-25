# Build English map links from the existing places and their translated posts.
module Jekyll
  class EnglishMap < Generator
    safe true
    def generate(site)
      translations = site.collections.fetch('en_posts').docs.each_with_object({}) do |post, index|
        index[post.data['kr_permalink']] = post
      end
      countries = {'usa'=>'United States', 'australia'=>'Australia', 'newzealand'=>'New Zealand', 'japan'=>'Japan', 'singapore'=>'Singapore', 'uk'=>'United Kingdom'}
      names = {'시애틀'=>'Seattle', '시드니'=>'Sydney', '오클랜드 / 크라이스트처치'=>'Auckland / Christchurch', '후쿠오카 / 유후인'=>'Fukuoka / Yufuin', '도쿄 / 하네다'=>'Tokyo / Haneda', '삿포로 / 조잔케이'=>'Sapporo / Jozankei', '싱가포르'=>'Singapore', '런던'=>'London'}
      site.data['en_places'] = site.data.fetch('places', []).filter_map do |place|
        posts = place.fetch('posts', []).filter_map do |entry|
          post = translations[entry['url']]
          {'title'=>post.data['title'], 'url'=>post.url} if post
        end
        next if posts.empty?
        place.merge('name'=>names.fetch(place['name']), 'country'=>countries.fetch(place['data_country']), 'posts'=>posts, 'post_count'=>posts.size)
      end
    end
  end
end
