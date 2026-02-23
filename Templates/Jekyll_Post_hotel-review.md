<%*
  let title = await tp.system.prompt("파일명 입력 (영문 소문자, 예: hilton-sydney)");
  await tp.file.rename(tp.date.now("YYYY-MM-DD") + "-" + title);
_%>
---
layout: post
title: "[숙박후기] "
date: <% tp.date.now("YYYY-MM-DD HH:mm:ss") %> +0900
category: hotel-review
tags:
  - 숙박
  - 
series: 
image: /assets/images/hotel-review/
---
