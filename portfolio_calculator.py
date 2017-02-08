import os.path
from tornado_jinja2 import Jinja2Loader
import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web
from jinja2 import *
import pandas as pd
import requests
import datetime
import tornado.web
import jinja2


from tornado.options import define, options
define("port", default=8000, help="run on the given port", type=int)

class IndexHandler(tornado.web.RequestHandler):
    def get(self):
        self.render('index.html')

class result_handler(tornado.web.RequestHandler):
    def post(self):
		now = datetime.datetime.now()
		base_url = 'http://ws.spk.gov.tr/PortfolioValues/api/PortfoyDegerleri'
		portfolio = pd.DataFrame({'Name': [],
		                          'Type': [],
		                          'Number': [],
		                          'Price': []})

		transactions = pd.DataFrame({'Name': [],
		                          'Type': [],
		                          'Number': [],
		                          'Tarih': []})

		name_= pd.Series(self.get_arguments('name[]' , strip=True))
		type_ = pd.Series(self.get_arguments('type[]', strip=True))
		number_ = pd.Series(self.get_arguments('number[]', strip=True))
		date_ = pd.Series(self.get_arguments('date[]', strip=True))
		transactions['Name'] = name_.values
		transactions['Type'] = type_.values
		transactions['Number'] = number_.values
		transactions['Tarih'] = date_.values
		closed_positions = pd.DataFrame({'Name': [],
		                         'B_Price': [],
		                         'S_Price': [],
		                         'Share#': [],
		                         'NetProfit': []})
		start = transactions['Tarih'][0]
		end = datetime.datetime.now().date()
		columns = transactions.Name.unique()
		date_stocks = pd.DataFrame(index=pd.date_range(start, end), columns=columns)

		for t in transactions.iterrows():
		    _name = t[1]['Name']
		    _type = t[1]['Type']
		    _number = int(t[1]['Number'])
		    _tarih = t[1]['Tarih']
		    resp = requests.get(base_url + "/" + _name + "/4/" + _tarih + "/" + _tarih)
		    for item in resp.json():
		        _price = item['BirimPayDegeri']

		    s = pd.Series([_name, _type, _number, _price], index=['Name', 'Type', 'Number', 'Price'])
		    if _type == 'BUY':
		        portfolio = portfolio.append(s, ignore_index=True)
		    else:
		        i = 0
		        while _number > 0:
		            if str(portfolio.ix[i, 'Name']) != str(_name):
		                i += 1
		                continue
		            if portfolio.ix[i, 'Number'] <= _number:
		                profit = portfolio.ix[i, 'Number'] * (_price - portfolio.ix[i, 'Price'])
		                s = pd.Series([_name,
		                               portfolio.ix[i, 'Price'],
		                               _price,
		                               portfolio.ix[i, 'Number'],
		                               profit], index=['Name', 'B_Price', 'S_Price', 'Share#', 'NetProfit'])
		                closed_positions = closed_positions.append(s, ignore_index=True)
		                _number = _number - portfolio.ix[i, 'Number']
		                portfolio.drop(portfolio.index[[i]], inplace=True)
		                portfolio.reset_index(drop=True, inplace=True)
		            else:
		                profit = _number * (_price - portfolio.ix[i, 'Price'])
		                s = pd.Series([_name,
		                               portfolio.ix[i, 'Price'],
		                               _price,
		                               _number,
		                               profit], index=['Name', 'B_Price', 'S_Price', 'Share#', 'NetProfit'])
		                closed_positions = closed_positions.append(s, ignore_index=True)
		                portfolio.ix[i, 'Number'] -= _number
		                _number = 0
		    for q in portfolio.iterrows():
		        date_stocks[q[1]['Name']][_tarih] = q[1]['Number']
		    for column in date_stocks:
		        if pd.isnull(date_stocks[column][_tarih]):
		            date_stocks[column][_tarih] = 0

		date_stocks = date_stocks.fillna(method='ffill')

		g = list(date_stocks.columns.values)

		for name_ in g:
		    resp = requests.get(base_url + "/" + name_ + "/4/" + str(start) + "/" + str(end))
		    columns = [str('Value' + name_)]
		    my_list = pd.DataFrame(index=pd.date_range(start, end), columns=columns)
		    for item in resp.json():
		        _price = item['BirimPayDegeri']
		        _tarih = item['Tarih'].split('T', 1)[0]
		        my_list[str('Value' + name_)][_tarih] = _price
		    my_list = my_list.fillna(method='ffill')
		    date_stocks = pd.concat([date_stocks, my_list], axis=1)

		date_stocks['TotalValue'] = 0

		for name_ in g:
		    date_stocks['TotalValue'] += date_stocks[name_] * date_stocks[str('Value' + name_)]

		portfolio['Value'] = portfolio.Number * portfolio.Price
		res_table = portfolio.to_html().replace('\n','')
		_profit = closed_positions['NetProfit'].sum()
		self.render('result.html',tables=res_table.to_html(),profit = _profit)

if __name__ == '__main__':
	jinja2_env = jinja2.Environment(loader=jinja2.FileSystemLoader('templates/'), autoescape=False)
	jinja2_loader = Jinja2Loader(jinja2_env)
	settings = dict(template_loader=jinja2_loader)
	tornado.options.parse_command_line()
	app = tornado.web.Application(
		handlers=[(r'/', IndexHandler), (r'/result', result_handler)],
		static_path=os.path.join(os.path.dirname(__file__), "static"),
		template_path=os.path.join(os.path.dirname(__file__), "templates"),**settings)
	http_server = tornado.httpserver.HTTPServer(app)
	http_server.listen(options.port)
	tornado.ioloop.IOLoop.instance().start()
