<%*
  let title = await tp.system.prompt("파일명 입력 (영문 소문자, 예: tokyo-day1)");
  await tp.file.rename(tp.date.now("YYYY-MM-DD") + "-" + title);
_%>
---
layout: post
title: "[여행후기] "
date: <% tp.date.now("YYYY-MM-DD HH:mm:ss") %> +0900
category: travel
tags:
  - 여행
  - 
series: 
image: /assets/images/travel/
---
