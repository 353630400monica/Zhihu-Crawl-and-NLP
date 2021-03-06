import json
import scrapy
from scrapy_redis.spiders import RedisSpider
from zhihui_redis.items import ZhihuiRedisItem
from scrapy import Request, FormRequest
import re

#用一个全局变量来做回答的ID
#a_id = 1

class MySpider(RedisSpider):
    name = "myspider"
    redis_key = 'myspider:start_urls'

    allowed_domains = ['zhihu.com']

    # def __init__(self, *args, **kwargs):
    #     domain = kwargs.pop('domain', '')
    #     self.allowed_domains = filter(None, domain.split(','))
    #     super(MySpider, self).__init__(*args, **kwargs)

    #以话题广场为入口，知乎中这里的请求为POST请求，所以使用FormRequest
    def parse(self,response):
        #inspect_response(response, self)#程序运行到这时会停下来，可用于检验response.xpath()语句是否能得到正确结果
        topics = response.xpath('//div[@class="zm-topic-cat-page"]/ul/li')
        for topic in topics:
            topic_name = topic.xpath('./a/text()').extract_first()
            topic_id = topic.xpath('./@data-id').extract_first()
            topic_url = "https://www.zhihu.com/node/TopicsPlazzaListV2"#post请求的网址
            yield FormRequest(url=topic_url,callback=self.parse_topic, dont_filter=True,
                              meta={"offset": 0, "topic_id": topic_id, "name": topic_name},
                              formdata={"method": "next",
                                        "_xsrf": "anaUqgXhz0GbjNTjnykooNIwJJuQz0CY",#遇到的坑：此处一定要加“xsrf"(cookies中的),否则会出现403错误
                                        "params": json.dumps({"topic_id": topic_id, "offset": 0, "hash_id": "5d6d053d9cca5b5d463f76e7f866080a"})})

    def parse_topic(self,response):#得到各个子话题的网址
        # 获取传递的变量
        offset = response.meta.get("offset")
        topic_id = response.meta.get("topic_id")
        topic_name = response.meta.get("name")
        # 解析获得的响应
        json_info = json.loads(response.text)  # 此时json_info为一个字典
        msg_info = json_info['msg']  # 键为 msg 的值对应为一个列表
        offset += len(msg_info)

        date = {"topic" : topic_name}

        # 判断 msg_info 里的 msg 数量是否小于20，小于的话表示已经是最后一页，就不再请求了
        for x in msg_info:
            child_id = re.search(r'\/topic\/(\d+)', x).group()
            id = re.search(r'(\d+)', child_id).group()  # 为下面的请求传所需要的参数
            url1 = 'https://www.zhihu.com/api/v4/topics/'  # 此处是topics而不是topic
            url2 = '/feeds/essence?include=data%5B%3F%28target.type%3Dtopic_sticky_module%29%5D.target.data%5B%3F%28target.type%3Danswer%29%5D.target.content%2Crelationship.is_authorized%2Cis_author%2Cvoting%2Cis_thanked%2Cis_nothelp%3Bdata%5B%3F%28target.type%3Dtopic_sticky_module%29%5D.target.data%5B%3F%28target.type%3Danswer%29%5D.target.is_normal%2Ccomment_count%2Cvoteup_count%2Ccontent%2Crelevant_info%2Cexcerpt.author.badge%5B%3F%28type%3Dbest_answerer%29%5D.topics%3Bdata%5B%3F%28target.type%3Dtopic_sticky_module%29%5D.target.data%5B%3F%28target.type%3Darticle%29%5D.target.content%2Cvoteup_count%2Ccomment_count%2Cvoting%2Cauthor.badge%5B%3F%28type%3Dbest_answerer%29%5D.topics%3Bdata%5B%3F%28target.type%3Dtopic_sticky_module%29%5D.target.data%5B%3F%28target.type%3Dpeople%29%5D.target.answer_count%2Carticles_count%2Cgender%2Cfollower_count%2Cis_followed%2Cis_following%2Cbadge%5B%3F%28type%3Dbest_answerer%29%5D.topics%3Bdata%5B%3F%28target.type%3Danswer%29%5D.target.annotation_detail%2Ccontent%2Chermes_label%2Cis_labeled%2Crelationship.is_authorized%2Cis_author%2Cvoting%2Cis_thanked%2Cis_nothelp%3Bdata%5B%3F%28target.type%3Danswer%29%5D.target.author.badge%5B%3F%28type%3Dbest_answerer%29%5D.topics%3Bdata%5B%3F%28target.type%3Darticle%29%5D.target.annotation_detail%2Ccontent%2Chermes_label%2Cis_labeled%2Cauthor.badge%5B%3F%28type%3Dbest_answerer%29%5D.topics%3Bdata%5B%3F%28target.type%3Dquestion%29%5D.target.annotation_detail%2Ccomment_count%3B&limit=10&offset=0'
            url = url1 + id + url2

            yield Request(url=url, callback=self.parseQuestions,meta=date)

        if not len(msg_info) < 20:
            yield FormRequest("https://www.zhihu.com/node/TopicsPlazzaListV2", callback=self.parse_topic,
                              dont_filter=True, meta={"offset": offset, "topic_id": topic_id, "name": topic_name},
                              formdata={"method": "next",
                                        "_xsrf" : "anaUqgXhz0GbjNTjnykooNIwJJuQz0CY",
                                        "params": json.dumps({"topic_id": topic_id, "offset": offset, "hash_id": "5d6d053d9cca5b5d463f76e7f866080a"})
                            })


    def parseQuestions(self,response):#得到问题的url
        #url的格式https://www.zhihu.com/question/id1/answer/id2
        topic = response.meta.get("topic")
        q_json = json.loads(str(response.body,'utf-8'))#将网页内容转化为JSON格式
        is_end = q_json["paging"]["is_end"]  # bool值看是不是最后一个问题
        next_url = q_json["paging"]["next"]  # 后续问题的网址
        list = q_json["data"]
        for dic in list:#遇到得坑：List中只有前六个数据是有用得
            if('question' in dic['target']):
                id1 = dic['target']['question']['id']#网址中的id1
                #id2 = dic['target']['id']#网址中的id2
                data = {"id" : id1, "topic": topic}
                url = 'https://www.zhihu.com/question/' + str(id1)
                yield Request(url=url,  callback=self.parseAnswers_json,meta=data,priority=40)

        if not is_end:
            yield Request(url=next_url, callback=self.parseQuestions,)


    def parseAnswers_json(self,response):#因为问题的浏览数和关注数不在JSON文件中所以新增一个请求
        id = response.meta.get("id")
        topic = response.meta.get("topic")#获取问题所属的话题
        #回答的JSON文件的网址
        url1 = 'https://www.zhihu.com/api/v4/questions/'
        url2 = '/answers?include=data%5B%2A%5D.is_normal%2Cadmin_closed_comment%2Creward_info%2Cis_collapsed%2Cannotation_action%2Cannotation_detail%2Ccollapse_reason%2Cis_sticky%2Ccollapsed_by%2Csuggest_edit%2Ccomment_count%2Ccan_comment%2Ccontent%2Ceditable_content%2Cvoteup_count%2Creshipment_settings%2Ccomment_permission%2Ccreated_time%2Cupdated_time%2Creview_info%2Crelevant_info%2Cquestion%2Cexcerpt%2Crelationship.is_authorized%2Cis_author%2Cvoting%2Cis_thanked%2Cis_nothelp%2Cis_labeled%2Cis_recognized%2Cpaid_info%2Cpaid_info_content%3Bdata%5B%2A%5D.mark_infos%5B%2A%5D.url%3Bdata%5B%2A%5D.author.follower_count%2Cbadge%5B%2A%5D.topics&limit=3&offset=0&platform=desktop&sort_by=default'
        url = url1 + str(id) + url2

        items = ZhihuiRedisItem()
        items['answer'] = []  # 初始化列表
        items['commend_count'] = []
        items['voteup'] = []
        items['a_id'] = []

        num = response.xpath('//strong[@class="NumberBoard-itemValue"]/@title').extract()#获取浏览数和关注数
        s = response.xpath('//span[@class="RichText ztext"]/text()').extract()#获取问题描述

        items['follow_count'] = num[0] # 问题关注数
        items['broswer_count'] = num[1] # 问题浏览数
        items['describe'] = "".join(s) #问题描述
        items['topic'] = topic

        yield Request(url=url, callback=self.parsePage, meta={'item': items},priority=50)

    def parsePage(self,response):#处理问题的回答
        #global a_id
        ans_json = json.loads(str(response.body, 'utf-8'))
        is_end = ans_json["paging"]["is_end"]  # bool值看是不是最后一个回答
        next_url = ans_json["paging"]["next"]  # 后续回答的网址
        items = response.meta.get('item')# 接收传的参数
        items['answer_count'] = ans_json['paging']['totals']  # 问题总回答数
        for answer in ans_json["data"]:#处理分析JSON网页文件
            items['title'] = answer['question']['title']  # 问题内容
            items['q_id'] = answer['question']['id'] # 问题ID

            #a_id += 1 #回答ID
            #items['a_id'].append(str(a_id))
            items['answer'].append(answer['content'])  # 回答内容
            items['commend_count'].append(answer['comment_count']) #评论数
            items['voteup'].append(answer['voteup_count'])  # 获赞数

        # 如果不是最后一个页面
        if not is_end:
                yield scrapy.Request(next_url, callback=self.parsePage, meta={'item': items},priority=100)
        else:
            yield items
